import pygame
import sys
import os
import math
import random
from collections import deque
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from core.graphics_utils import load_texture
from core.renderer import draw_cube, draw_floor_tile, draw_u_stairs, draw_computer, draw_tooltip, draw_collectible
from core.physics_engine import (BLOCK_SIZE, WALL_HEIGHT, is_wall, 
                                 has_ramp_below, get_target_y)
from core.ui import Button, Title
import core.save_manager as save_manager
from core.monster import MazeMonster

LOG_PATH = os.path.join(os.path.dirname(__file__), 'game_debug.log')
RANDOM_H_COUNT = 5

def log_debug(message):
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as log_file:
            log_file.write(message + '\n')
    except Exception:
        pass


def log_level_matrix(level_map, layer_index, header):
    if not (0 <= layer_index < len(level_map)):
        return
    log_debug(header)
    for row in level_map[layer_index]:
        log_debug(''.join(row))

# iniciando uma "câmera" em primeira pessoa
def init_opengl_fps(width, height):
    glViewport(0, 0, int(width), int(height))
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(75, (width / height), 0.1, 1000.0)
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)
    
    # desliga transparências antigas do hub para evitar bugs de renderização nas paredes
    glDisable(GL_BLEND)


def world_to_grid(position):
    x, z = position
    row = int(round(z / BLOCK_SIZE))
    col = int(round(x / BLOCK_SIZE))
    return row, col


def grid_to_world(row, col):
    return col * BLOCK_SIZE, row * BLOCK_SIZE


def is_grid_walkable(char):
    return char is not None and char not in ['P', ' ']


def get_cell(level_map, layer_index, row, col):
    if not (0 <= layer_index < len(level_map)):
        return None
    floor = level_map[layer_index]
    if not (0 <= row < len(floor)):
        return None
    if not (0 <= col < len(floor[row])):
        return None
    return floor[row][col]


def world_to_grid_3d(position):
    layer, x, z = position
    row, col = world_to_grid((x, z))
    return layer, row, col


def navigation_distance(a, b):
    layer_penalty = abs(a[0] - b[0]) * BLOCK_SIZE * 4.0
    return math.hypot(a[1] - b[1], a[2] - b[2]) + layer_penalty


def pathfinder_floor(level_map, start, target):
    start_layer, start_row, start_col = world_to_grid_3d(start)
    target_layer, target_row, target_col = world_to_grid_3d(target)

    if start_layer != target_layer:
        return [(start_layer, start_row, start_col)]

    if not is_grid_walkable(get_cell(level_map, start_layer, start_row, start_col)):
        return [(start_layer, start_row, start_col)]

    visited = {(start_layer, start_row, start_col): None}
    queue = deque([(start_layer, start_row, start_col)])

    while queue:
        layer, row, col = queue.popleft()
        if (layer, row, col) == (target_layer, target_row, target_col):
            break

        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = row + dr, col + dc
            node = (layer, nr, nc)
            if node in visited:
                continue
            if is_grid_walkable(get_cell(level_map, layer, nr, nc)):
                visited[node] = (layer, row, col)
                queue.append(node)

    if (target_layer, target_row, target_col) not in visited:
        return [(start_layer, start_row, start_col)]

    path = []
    current = (target_layer, target_row, target_col)
    while current is not None:
        path.append(current)
        current = visited[current]
    path.reverse()
    return path


def find_nearest_walkable(level_map, layer_index, start_row, start_col):
    floor = level_map[layer_index] if level_map and 0 <= layer_index < len(level_map) else level_map[0] if level_map else []
    rows = len(floor)
    if rows == 0:
        return None

    start_row = max(0, min(start_row, rows - 1))
    start_col = max(0, min(start_col, len(floor[start_row]) - 1))

    if is_grid_walkable(floor[start_row][start_col]):
        return (start_row, start_col)

    visited = {(start_row, start_col)}
    queue = deque([(start_row, start_col)])

    while queue:
        row, col = queue.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = row + dr, col + dc
            if (nr, nc) in visited:
                continue
            if 0 <= nr < rows and 0 <= nc < len(floor[nr]):
                if is_grid_walkable(floor[nr][nc]):
                    return (nr, nc)
                visited.add((nr, nc))
                queue.append((nr, nc))
    return None


def build_layer_monster_spawns(level_map, layer_index, existing_spawns, desired_count=3):
    floor = level_map[layer_index] if level_map and 0 <= layer_index < len(level_map) else []
    rows = len(floor)
    spawns = list(existing_spawns)

    # candidate regions para patrulha espalhada
    targets = [
        (2, 2),
        (2, len(floor[0]) - 3 if floor and len(floor[0]) > 3 else 2),
        (rows - 3, len(floor[0]) // 2 if floor and len(floor[0]) else 2),
    ]

    for target_row, target_col in targets:
        if len(spawns) >= desired_count:
            break
        candidate = find_nearest_walkable(level_map, layer_index, target_row, target_col)
        if candidate and candidate not in spawns:
            spawns.append(candidate)

    if len(spawns) < desired_count:
        for row in range(rows):
            for col in range(len(floor[row])):
                if len(spawns) >= desired_count:
                    break
                if is_grid_walkable(floor[row][col]) and (row, col) not in spawns:
                    spawns.append((row, col))
            if len(spawns) >= desired_count:
                break

    return spawns[:desired_count]


def collect_walkable_cells(level_map, layer_index):
    floor = level_map[layer_index] if level_map and 0 <= layer_index < len(level_map) else []
    cells = []
    for row, line in enumerate(floor):
        for col, char in enumerate(line):
            if char == '.':
                cells.append((row, col))
    return cells


def choose_random_cells_far_from_origin(cells, origin_cell, amount, min_distance):
    if not origin_cell:
        random.shuffle(cells)
        return cells[:amount]

    far_cells = [
        cell for cell in cells
        if abs(cell[0] - origin_cell[0]) + abs(cell[1] - origin_cell[1]) >= min_distance
    ]
    source = far_cells if len(far_cells) >= amount else cells
    random.shuffle(source)
    return source[:amount]


def cutoff_target(level_map, player_position, monster_position, predicted_target, layer_index=0):
    target_layer, target_x, target_z = predicted_target
    row, col = world_to_grid((target_x, target_z))
    if is_grid_walkable(get_cell(level_map, target_layer, row, col)):
        return predicted_target
    return player_position


def draw_stamina_bar(stamina, max_stamina, width, height):
    bar_width = 340
    bar_height = 26
    padding = 10
    x = padding
    y = height - bar_height - padding
    fill_width = int((stamina / max_stamina) * (bar_width - 4))

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glDisable(GL_TEXTURE_2D)

    # background
    glColor3f(0.1, 0.1, 0.1)
    glBegin(GL_QUADS)
    glVertex2f(x, y)
    glVertex2f(x + bar_width, y)
    glVertex2f(x + bar_width, y + bar_height)
    glVertex2f(x, y + bar_height)
    glEnd()

    # border
    glColor3f(0.8, 0.8, 0.8)
    glLineWidth(2.0)
    glBegin(GL_LINE_LOOP)
    glVertex2f(x, y)
    glVertex2f(x + bar_width, y)
    glVertex2f(x + bar_width, y + bar_height)
    glVertex2f(x, y + bar_height)
    glEnd()

    # fill
    glColor3f(0.0, 0.7, 0.3)
    glBegin(GL_QUADS)
    glVertex2f(x + 2, y + 2)
    glVertex2f(x + 2 + fill_width, y + 2)
    glVertex2f(x + 2 + fill_width, y + bar_height - 2)
    glVertex2f(x + 2, y + bar_height - 2)
    glEnd()

    glEnable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()


def draw_center_message(message, width, height, font, text_color, bg_color=(20, 20, 20)):
    text_surface = font.render(f"  {message}  ", True, text_color, bg_color)
    text_width, text_height = text_surface.get_size()
    image_data = pygame.image.tostring(text_surface, "RGBA", True)

    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, text_width, text_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, image_data)

    pos_x = (width - text_width) / 2
    pos_y = (height - text_height) / 2

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glColor3f(1.0, 1.0, 1.0)

    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 1.0); glVertex2f(pos_x, pos_y)
    glTexCoord2f(1.0, 1.0); glVertex2f(pos_x + text_width, pos_y)
    glTexCoord2f(1.0, 0.0); glVertex2f(pos_x + text_width, pos_y + text_height)
    glTexCoord2f(0.0, 0.0); glVertex2f(pos_x, pos_y + text_height)
    glEnd()

    glDisable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()

    glDeleteTextures(1, [tex_id])


def show_end_screen(message, width, height, font, duration_ms=1800, text_color=(120, 255, 120)):
    start_time = pygame.time.get_ticks()

    while pygame.time.get_ticks() - start_time < duration_ms:
        for event in pygame.event.get():
            if event.type == QUIT:
                return "QUIT"

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        draw_center_message(message, width, height, font, text_color)
        pygame.display.flip()
        pygame.time.delay(16)

    return "DONE"


def draw_h_counter(collected, total, width, height):
    if total <= 0:
        return

    icon_size = 28
    spacing = 10
    start_x = width - ((icon_size + spacing) * total) - 130
    y = height - 46

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glDisable(GL_TEXTURE_2D)

    for index in range(total):
        x = start_x + index * (icon_size + spacing)
        color = (1.0, 0.93, 0.45) if index < collected else (0.35, 0.32, 0.18)
        glColor3f(*color)
        glBegin(GL_TRIANGLES)
        glVertex2f(x + (icon_size / 2), y)
        glVertex2f(x, y + icon_size)
        glVertex2f(x + icon_size, y + icon_size)
        glEnd()

    glEnable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()


def update_sprint_stamina(stamina, max_stamina, wants_to_sprint, dt):
    stamina_depletion_rate = max_stamina / 3.0
    stamina_recharge_rate = max_stamina / 3.75

    sprinting = wants_to_sprint and stamina > 0.05

    if sprinting:
        stamina -= stamina_depletion_rate * dt
        if stamina < 0.0:
            stamina = 0.0
            sprinting = False
    else:
        if stamina < max_stamina:
            stamina += stamina_recharge_rate * dt
            if stamina > max_stamina:
                stamina = max_stamina

    return stamina, sprinting

# loop principal
def start(planet, saved_state=None):
    screen_info = pygame.display.Info()
    screen_width = screen_info.current_w
    screen_height = screen_info.current_h
    
    # garante que o contexto OpenGL está limpo e focado
    pygame.display.set_mode((screen_width, screen_height), DOUBLEBUF | OPENGL)
    
    init_opengl_fps(screen_width, screen_height)
    
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)
    pygame.event.clear()
    pygame.mouse.get_rel()
    pygame.font.init()
    hud_font = pygame.font.SysFont("Arial", 18, bold=True)
    end_font = pygame.font.SysFont("Arial", 42, bold=True)
    center_hud_font = pygame.font.SysFont("Arial", 30, bold=True)
    
    log_debug(f"[game_template] start planet={planet.name}, surface={pygame.display.get_surface() is not None}")
    print(f"[game_template] start planet={planet.name}, surface={pygame.display.get_surface() is not None}")
    
    clock = pygame.time.Clock()
    FPS = 60
    level_start_time = pygame.time.get_ticks()

    # Carregamento de texturas — caminho correto para a raiz do projeto
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    textures_dir = os.path.join(project_root, "Assets", "Textures")
    floor_texture_id = None
    wall_texture_id = None
    if planet.name in ("Cyber", "Ciber"):
        floor_texture_id = load_texture(os.path.join(textures_dir, "cyberchao.png"), max_size=128)
        wall_texture_id = load_texture(os.path.join(textures_dir, "cyberwall.png"), max_size=128)

    current_map = [[list(row) for row in floor] for floor in planet.layout]
    monster_spawns_by_layer = {y_index: [] for y_index in range(len(current_map))}

    # encontra o '@' (spawn) e os pontos de monstro na matriz 3D
    cam_x = 0.0
    cam_y = WALL_HEIGHT + 2.0
    cam_z = 0.0
    found_spawn = False
    exit_position = None
    spawn_cell = None
    collected_h_points = 0
    for y_index, andar in enumerate(current_map):
        for z_index, linha in enumerate(andar):
            for x_index, char in enumerate(linha):
                if char == '@':
                    cam_x = x_index * BLOCK_SIZE
                    cam_y = (y_index * WALL_HEIGHT) + 2.0 # altura da câmera baseada no andar
                    cam_z = z_index * BLOCK_SIZE
                    spawn_cell = (y_index, z_index, x_index)
                    current_map[y_index][z_index][x_index] = '.'
                    found_spawn = True
                if planet.name in ("Cyber", "Ciber") and char == 'M':
                    monster_spawns_by_layer[y_index].append((z_index, x_index))
                    current_map[y_index][z_index][x_index] = '.'
                if char == 'Q':
                    exit_position = (y_index, z_index, x_index)
                if char == 'H':
                    current_map[y_index][z_index][x_index] = '.'

    if not found_spawn and current_map:
        for z_index, linha in enumerate(current_map[0]):
            for x_index, char in enumerate(linha):
                if char == '.':
                    cam_x = x_index * BLOCK_SIZE
                    cam_y = WALL_HEIGHT + 2.0
                    cam_z = z_index * BLOCK_SIZE
                    found_spawn = True
                    break
            if found_spawn:
                break

    # cria a variável de altura lógica copiando a altura inicial
    player_y = cam_y

    total_h_points = 0
    if planet.name in ("Cyber", "Ciber") and spawn_cell:
        pickup_layer = spawn_cell[0]
        walkable_cells = collect_walkable_cells(current_map, pickup_layer)
        if exit_position and exit_position[0] == pickup_layer:
            exit_cell = (exit_position[1], exit_position[2])
            walkable_cells = [cell for cell in walkable_cells if cell != exit_cell]
        random_h_cells = choose_random_cells_far_from_origin(
            walkable_cells,
            (spawn_cell[1], spawn_cell[2]),
            amount=min(RANDOM_H_COUNT, len(walkable_cells)),
            min_distance=8,
        )
        for row, col in random_h_cells:
            current_map[pickup_layer][row][col] = 'H'
        total_h_points = len(random_h_cells)
        log_level_matrix(
            current_map,
            pickup_layer,
            f"[game_template] matriz do andar {pickup_layer} apos gerar H ({total_h_points} itens):"
        )

    monsters = []
    if planet.name in ("Cyber", "Ciber"):
        spawn_layer_index = 0
        walkable_cells = collect_walkable_cells(current_map, spawn_layer_index)
        if spawn_cell and spawn_cell[0] == spawn_layer_index:
            walkable_cells = [
                cell for cell in walkable_cells
                if cell != (spawn_cell[1], spawn_cell[2])
            ]
        all_spawn_points = [
            (spawn_layer_index, row, col)
            for row, col in choose_random_cells_far_from_origin(
                walkable_cells,
                (spawn_cell[1], spawn_cell[2]) if spawn_cell and spawn_cell[0] == spawn_layer_index else None,
                amount=min(4, len(walkable_cells)),
                min_distance=10,
            )
        ]

        monster_profiles = [
            ("blinky", "Blinky", (0.45, 0.08, 0.18)),
            ("pinky", "Pinky", (0.08, 0.12, 0.35)),
            ("inky", "Inky", (0.22, 0.08, 0.32)),
            ("clyde", "Clyde", (0.82, 0.08, 0.08)),
        ]

        for index, (personality, display_name, color) in enumerate(monster_profiles):
            if index >= len(all_spawn_points):
                break

            layer_index, spawn_row, spawn_col = all_spawn_points[index]
            spawn_position = grid_to_world(spawn_row, spawn_col)
            patrol_positions = []
            for dr, dc in ((0, 4), (4, 0), (0, -4), (-4, 0)):
                candidate = find_nearest_walkable(current_map, layer_index, spawn_row + dr, spawn_col + dc)
                if candidate and candidate != (spawn_row, spawn_col):
                    patrol_positions.append(grid_to_world(candidate[0], candidate[1]))
            patrol_positions = [spawn_position] + patrol_positions[:3]

            monster = MazeMonster(
                spawn_position,
                BLOCK_SIZE,
                navigation_distance,
                pathfinder_floor,
                cutoff_target,
                grid_to_world,
            )
            monster.current_layer = layer_index
            monster.patrol_points = patrol_positions
            monster.personality = personality
            monster.display_name = display_name
            monster.color = color
            monster.reveal(3, pygame.time.get_ticks())
            monsters.append(monster)

    yaw = 0.0   
    pitch = 0.0 
    
    mouse_sensitivity = 0.15
    base_move_speed = 0.15
    sprint_speed = 0.28
    player_radius = 0.4 # tamanho do "corpo" do jogador para colisão não ficar muito justa na parede

    stamina_max = 3.0
    stamina = stamina_max
    dt = 1.0 / FPS

    def is_player_collision(x, z, y):
        for dx in (-player_radius, 0.0, player_radius):
            for dz in (-player_radius, 0.0, player_radius):
                if is_wall(x + dx, y, z + dz, current_map):
                    return True
        return False

    def collect_all_h_points():
        nonlocal collected_h_points
        for layer_index, floor in enumerate(current_map):
            for row_index, line in enumerate(floor):
                for col_index, char in enumerate(line):
                    if char == 'H':
                        current_map[layer_index][row_index][col_index] = '.'
        collected_h_points = total_h_points
        log_debug(f"[game_template] debug coletou todos os H {collected_h_points}/{total_h_points}")

    def collect_one_h_point():
        nonlocal collected_h_points
        if collected_h_points >= total_h_points:
            return
        for layer_index, floor in enumerate(current_map):
            for row_index, line in enumerate(floor):
                for col_index, char in enumerate(line):
                    if char == 'H':
                        current_map[layer_index][row_index][col_index] = '.'
                        collected_h_points += 1
                        log_debug(f"[game_template] debug coletou 1 H {collected_h_points}/{total_h_points}")
                        return

    def teleport_to_exit():
        nonlocal cam_x, cam_y, cam_z, player_y
        if not exit_position:
            return
        exit_layer, exit_row, exit_col = exit_position
        exit_x, exit_z = grid_to_world(exit_row, exit_col)
        cam_x = exit_x
        cam_z = exit_z - (BLOCK_SIZE * 1.2)
        player_y = (exit_layer * WALL_HEIGHT) + 2.0
        cam_y = player_y
        log_debug("[game_template] debug teleportou para perto do Q")

    # --- Restauração de estado salvo ---
    if saved_state:
        cam_x = saved_state.get('cam_x', cam_x)
        cam_y = saved_state.get('cam_y', cam_y)
        cam_z = saved_state.get('cam_z', cam_z)
        player_y = saved_state.get('player_y', player_y)
        yaw = saved_state.get('yaw', 0.0)
        pitch = saved_state.get('pitch', 0.0)
        stamina = saved_state.get('stamina', stamina_max)
        collected_h_points = saved_state.get('collected_h_points', 0)
        # Restaura mapa (posições dos H coletados)
        if 'current_map' in saved_state:
            current_map = saved_state['current_map']
        # Restaura posição dos monstros
        if 'monsters_data' in saved_state:
            for i, mdata in enumerate(saved_state['monsters_data']):
                if i < len(monsters):
                    monsters[i].x = mdata.get('x', monsters[i].x)
                    monsters[i].z = mdata.get('z', monsters[i].z)

    running = True
    is_paused = False
    is_game_over = False
    is_victory = False
    esc_held = False
    result_state = "MENU"

    # --- Fontes e UI do menu de pausa ---
    try:
        fonte_botao = pygame.font.SysFont('consolas', 28, bold=True)
    except Exception:
        fonte_botao = pygame.font.SysFont('Arial', 28, bold=True)
    fonte_titulo = pygame.font.SysFont('Arial', 72, bold=True)

    # -- OTIMIZAÇÃO: COMPILAÇÃO DA DISPLAY LIST --
    mapa_display_list = glGenLists(1)
    glNewList(mapa_display_list, GL_COMPILE)
    for y_index, andar in enumerate(current_map):
        for z_index, linha in enumerate(andar):
            for x_index, char in enumerate(linha):
                if char == ' ': continue
                block_x = x_index * BLOCK_SIZE
                block_y = y_index * WALL_HEIGHT
                block_z = z_index * BLOCK_SIZE

                if char != ' ' and not has_ramp_below(y_index, z_index, x_index, current_map):
                    draw_floor_tile(block_x, block_y, block_z, BLOCK_SIZE, texture_id=floor_texture_id)

                if char == 'P':
                    draw_cube(block_x, block_y, block_z, BLOCK_SIZE, WALL_HEIGHT, texture_id=wall_texture_id)
                    draw_floor_tile(block_x, block_y + WALL_HEIGHT - 0.01, block_z, BLOCK_SIZE, texture_id=floor_texture_id)
                elif char == 'V':
                    glEnable(GL_BLEND)
                    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                    # Note: O usuário não mencionou draw_textured_cube com vidro aqui para Cyber, 
                    # mas vamos deixá-lo invisível se for 'pass' original, ou desenhar cube. Em cyber.py tava pass
                    pass
                elif char in ['<', '>', '^', 'v']:
                    draw_u_stairs(block_x, block_y, block_z, BLOCK_SIZE, WALL_HEIGHT, char, texture_id=floor_texture_id)
                elif char == 'M':
                    draw_computer(block_x, block_y, block_z, BLOCK_SIZE, WALL_HEIGHT)
    glEndList()
    # --------------------------------------------

    _btn_color = (0, 0, 0, 0)
    _font_btn_color = (95, 198, 139, 255)
    _hover_btn_color = (95, 198, 139, 150)

    title_pause = Title(
        screen_width // 2 - 300, screen_height // 2 - 200, 600, 100,
        "PAUSADO", fonte_titulo, bg_color=(0, 0, 0, 0),
        text_color=(255, 255, 255, 255), align="center"
    )

    def cb_continuar():
        nonlocal is_paused
        is_paused = False
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        pygame.mouse.get_rel()

    def cb_salvar_jogo():
        level_data = {
            'planet_name': planet.name,
            'cam_x': cam_x,
            'cam_y': cam_y,
            'cam_z': cam_z,
            'player_y': player_y,
            'yaw': yaw,
            'pitch': pitch,
            'stamina': stamina,
            'collected_h_points': collected_h_points,
            'current_map': current_map,
            'monsters_data': [{'x': m.x, 'z': m.z, 'spawn_layer': m.spawn_layer} for m in monsters],
        }
        save_manager.save_level_save(planet.name, level_data)
        main = save_manager.load_main_save()
        save_manager.save_main_save(main.get('unlocked_planets', []), planet.name)
        cb_continuar()

    def cb_carregar_jogo():
        nonlocal running, result_state
        result_state = "LOAD_GAME"
        running = False

    def cb_voltar_menu():
        nonlocal running, result_state
        result_state = "MENU"
        running = False

    def cb_sair_desktop():
        pygame.quit()
        sys.exit()

    def cb_restart_level():
        nonlocal running, result_state
        result_state = "RESTART"
        running = False
        
    def cb_win_continue():
        nonlocal running, result_state
        result_state = "WIN_CONTINUE"
        running = False

    title_victory = Title(
        screen_width // 2 - 300, screen_height // 2 - 200, 600, 100,
        "VITÓRIA", fonte_titulo, bg_color=(0, 0, 0, 0),
        text_color=(50, 255, 50, 255), align="center"
    )
    btn_win_continue = Button(
        screen_width // 2 - 150, screen_height // 2 - 50, 300, 50, "CONTINUAR",
        fonte_botao, cb_win_continue, base_color=_btn_color,
        hover_color=_hover_btn_color, text_color=_font_btn_color
    )
    btn_win_menu = Button(
        screen_width // 2 - 150, screen_height // 2 + 20, 300, 50, "VOLTAR AO MENU",
        fonte_botao, cb_voltar_menu, base_color=_btn_color,
        hover_color=_hover_btn_color, text_color=_font_btn_color
    )
    btn_win_exit = Button(
        screen_width // 2 - 150, screen_height // 2 + 90, 300, 50, "SAIR",
        fonte_botao, cb_sair_desktop, base_color=_btn_color,
        hover_color=_hover_btn_color, text_color=_font_btn_color
    )

    btn_continue = Button(
        screen_width // 2 - 150, screen_height // 2 - 100, 300, 50, "CONTINUAR",
        fonte_botao, cb_continuar, base_color=_btn_color,
        hover_color=_hover_btn_color, text_color=_font_btn_color
    )
    btn_save = Button(
        screen_width // 2 - 150, screen_height // 2 - 30, 300, 50, "SALVAR",
        fonte_botao, cb_salvar_jogo, base_color=_btn_color,
        hover_color=_hover_btn_color, text_color=_font_btn_color
    )
    btn_load = Button(
        screen_width // 2 - 150, screen_height // 2 + 40, 300, 50, "CARREGAR",
        fonte_botao, cb_carregar_jogo, base_color=_btn_color,
        hover_color=_hover_btn_color, text_color=_font_btn_color
    )
    btn_menu = Button(
        screen_width // 2 - 150, screen_height // 2 + 110, 300, 50, "VOLTAR AO MENU",
        fonte_botao, cb_voltar_menu, base_color=_btn_color,
        hover_color=_hover_btn_color, text_color=_font_btn_color
    )
    btn_exit = Button(
        screen_width // 2 - 150, screen_height // 2 + 180, 300, 50, "SAIR",
        fonte_botao, cb_sair_desktop, base_color=_btn_color,
        hover_color=_hover_btn_color, text_color=_font_btn_color
    )

    title_game_over = Title(
        screen_width // 2 - 300, screen_height // 2 - 200, 600, 100,
        "VOCÊ PERDEU", fonte_titulo, bg_color=(0, 0, 0, 0),
        text_color=(255, 50, 50, 255), align="center"
    )
    btn_restart_go = Button(
        screen_width // 2 - 150, screen_height // 2 - 100, 300, 50, "TENTAR DE NOVO",
        fonte_botao, cb_restart_level, base_color=_btn_color,
        hover_color=_hover_btn_color, text_color=_font_btn_color
    )

    while running:
        # --- Toggle pausa com ESC ---
        keys_raw = pygame.key.get_pressed()
        if not is_game_over and not is_victory:
            if keys_raw[K_ESCAPE] and not esc_held:
                esc_held = True
                if is_paused:
                    cb_continuar()
                else:
                    is_paused = True
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
            elif not keys_raw[K_ESCAPE]:
                esc_held = False

        mouse_pos = pygame.mouse.get_pos()
        if is_game_over:
            btn_restart_go.check_hover(mouse_pos)
            btn_load.check_hover(mouse_pos)
            btn_menu.check_hover(mouse_pos)
            btn_exit.check_hover(mouse_pos)
        elif is_victory:
            btn_win_continue.check_hover(mouse_pos)
            btn_win_menu.check_hover(mouse_pos)
            btn_win_exit.check_hover(mouse_pos)
        elif is_paused:
            btn_continue.check_hover(mouse_pos)
            btn_save.check_hover(mouse_pos)
            btn_load.check_hover(mouse_pos)
            btn_menu.check_hover(mouse_pos)
            btn_exit.check_hover(mouse_pos)

        # leitor de eventos
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()

            if is_game_over:
                btn_restart_go.handle_event(event)
                btn_load.handle_event(event)
                btn_menu.handle_event(event)
                btn_exit.handle_event(event)
            elif is_victory:
                btn_win_continue.handle_event(event)
                btn_win_menu.handle_event(event)
                btn_win_exit.handle_event(event)
            elif is_paused:
                btn_continue.handle_event(event)
                btn_save.handle_event(event)
                btn_load.handle_event(event)
                btn_menu.handle_event(event)
                btn_exit.handle_event(event)
                
            if event.type == KEYDOWN:
                if not is_paused and not is_game_over and not is_victory and event.key == K_p:
                    is_victory = True
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
                    continue

            if not is_paused and not is_game_over and event.type == KEYDOWN:
                if event.key == K_o:
                    collect_all_h_points()
                elif event.key == K_m:
                    teleport_to_exit()

        if is_paused or is_game_over or is_victory:
            pass  # Pula lógica de jogo — vai direto pra renderização
        else:
            # mantem a posição anterior para a IA do monstro
            prev_cam_x, prev_cam_z = cam_x, cam_z

            # movimento do mouse na câmera
            mouse_dx, mouse_dy = pygame.mouse.get_rel()
            yaw += mouse_dx * mouse_sensitivity
            pitch += mouse_dy * mouse_sensitivity
            
            if pitch > 89.0: pitch = 89.0
            if pitch < -89.0: pitch = -89.0

            # movimento do teclado e colisão
            keys = pygame.key.get_pressed()
            yaw_rad = math.radians(yaw)
            
            wants_to_sprint = keys[K_LSHIFT] or keys[K_RSHIFT]
            stamina, sprinting = update_sprint_stamina(stamina, stamina_max, wants_to_sprint, dt)
            move_speed = sprint_speed if sprinting else base_move_speed

            # vetores de direção matemática
            front_x = math.sin(yaw_rad)
            front_z = -math.cos(yaw_rad)
            right_x = math.cos(yaw_rad)
            right_z = math.sin(yaw_rad)

            # variáveis temporárias para testar a colisão antes de mover a câmera oficial
            next_x = cam_x
            next_z = cam_z

            if keys[K_w]:
                next_x += front_x * move_speed
                next_z += front_z * move_speed
            if keys[K_s]:
                next_x -= front_x * move_speed
                next_z -= front_z * move_speed
            if keys[K_a]:
                next_x -= right_x * move_speed
                next_z -= right_z * move_speed
            if keys[K_d]:
                next_x += right_x * move_speed
                next_z += right_z * move_speed

            # verificação de colisão eixo por eixo: testa o corpo inteiro do jogador
            if not is_player_collision(next_x, cam_z, player_y):
                cam_x = next_x
            if not is_player_collision(cam_x, next_z, player_y):
                cam_z = next_z

            # aplicação da lógica usada nas escadas e na gravidade
            player_y = get_target_y(cam_x, player_y, cam_z, current_map)
            player_layer = max(0, min(int(round((player_y - 2.0) / WALL_HEIGHT)), len(current_map) - 1))
            player_row, player_col = world_to_grid((cam_x, cam_z))
            current_cell = get_cell(current_map, player_layer, player_row, player_col)

            if current_cell == 'H':
                current_map[player_layer][player_row][player_col] = '.'
                collected_h_points += 1
                log_debug(f"[game_template] H coletado {collected_h_points}/{total_h_points}")

            if exit_position == (player_layer, player_row, player_col) and collected_h_points >= total_h_points:
                if not is_victory:
                    is_victory = True
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
                continue
            
            # a câmera visual persegue a física real suavemente
            cam_y += (player_y - cam_y) * 0.15

            if monsters:
                current_time = pygame.time.get_ticks()
                # blinky_position logic foi removida pois não há suporte na classe base
                for monster in monsters:
                    monster_result = monster.update(
                        current_map,
                        (player_layer, cam_x, cam_z),
                        (player_layer, prev_cam_x, prev_cam_z),
                        max(1, collected_h_points),
                        [],
                        (player_layer, cam_x, cam_z),
                        current_time,
                    )
                    if monster_result.caught_player:
                        log_debug(f"[game_template] player caught by monster")
                        is_game_over = True
                        pygame.mouse.set_visible(True)
                        pygame.event.set_grab(False)
                        break

        # renderização
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        animation_time = pygame.time.get_ticks() / 1000.0
        
        glRotatef(pitch, 1, 0, 0) 
        glRotatef(yaw, 0, 1, 0)   
        glTranslatef(-cam_x, -cam_y, -cam_z)

        # Desenha arquitetura estática da Display List
        glCallList(mapa_display_list)

        # percorre a matriz 3D apenas para os elementos dinâmicos (H e Q)
        for y_index, andar in enumerate(current_map):
            for z_index, linha in enumerate(andar):
                for x_index, char in enumerate(linha):
                    if char not in ['H', 'Q']:
                        continue

                    block_x = x_index * BLOCK_SIZE
                    block_y = y_index * WALL_HEIGHT
                    block_z = z_index * BLOCK_SIZE

                    if char == 'H':
                        draw_collectible(
                            block_x,
                            block_y + (WALL_HEIGHT * 0.2),
                            block_z,
                            BLOCK_SIZE * 0.45,
                            rotation_angle=(animation_time * 120.0) % 360.0,
                            hover_offset=math.sin(animation_time * 3.0 + (x_index * 0.35) + (z_index * 0.2)) * 0.25,
                            color=(1.0, 0.93, 0.45),
                        )
                    elif char == 'Q':
                        draw_cube(
                            block_x,
                            block_y,
                            block_z,
                            BLOCK_SIZE * 0.7,
                            WALL_HEIGHT * 0.35,
                            color=(0.1, 0.9, 0.2) if collected_h_points >= total_h_points else (0.25, 0.4, 0.25),
                        )

        if monsters:
            for monster in monsters:
                glPushMatrix()
                draw_cube(
                    monster.x,
                    monster.current_layer * WALL_HEIGHT,
                    monster.z,
                    BLOCK_SIZE * 0.38,
                    BLOCK_SIZE * 0.6,
                    color=monster.color,
                )
                glPopMatrix()

        draw_stamina_bar(stamina, stamina_max, screen_width, screen_height)
        draw_h_counter(collected_h_points, total_h_points, screen_width, screen_height)
        if pygame.time.get_ticks() - level_start_time <= 2000:
            draw_center_message("Encontre todos os pontos", screen_width, screen_height, center_hud_font, (255, 255, 255))

        # --- RENDERIZAÇÃO DO MENU DE PAUSA / GAME OVER / VITÓRIA ---
        if is_game_over:
            glMatrixMode(GL_PROJECTION)
            glPushMatrix()
            glLoadIdentity()
            glOrtho(0, screen_width, screen_height, 0, -1, 1)
            glMatrixMode(GL_MODELVIEW)
            glPushMatrix()
            glLoadIdentity()
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            glColor4f(0.5, 0, 0, 0.4)
            glBegin(GL_QUADS)
            glVertex2f(0, 0); glVertex2f(screen_width, 0)
            glVertex2f(screen_width, screen_height); glVertex2f(0, screen_height)
            glEnd()
            
            title_game_over.draw()
            btn_restart_go.draw()
            btn_load.draw()
            btn_menu.draw()
            btn_exit.draw()

            glEnable(GL_DEPTH_TEST)
            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)
            glPopMatrix()

        elif is_victory:
            glMatrixMode(GL_PROJECTION)
            glPushMatrix()
            glLoadIdentity()
            glOrtho(0, screen_width, screen_height, 0, -1, 1)
            glMatrixMode(GL_MODELVIEW)
            glPushMatrix()
            glLoadIdentity()
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            glColor4f(0, 0.5, 0, 0.4)
            glBegin(GL_QUADS)
            glVertex2f(0, 0); glVertex2f(screen_width, 0)
            glVertex2f(screen_width, screen_height); glVertex2f(0, screen_height)
            glEnd()
            
            title_victory.draw()
            btn_win_continue.draw()
            btn_win_menu.draw()
            btn_win_exit.draw()

            glEnable(GL_DEPTH_TEST)
            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)
            glPopMatrix()

        elif is_paused:
            glMatrixMode(GL_PROJECTION)
            glPushMatrix()
            glLoadIdentity()
            glOrtho(0, screen_width, screen_height, 0, -1, 1)
            glMatrixMode(GL_MODELVIEW)
            glPushMatrix()
            glLoadIdentity()
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            glColor4f(0, 0, 0, 0.6)
            glBegin(GL_QUADS)
            glVertex2f(0, 0); glVertex2f(screen_width, 0)
            glVertex2f(screen_width, screen_height); glVertex2f(0, screen_height)
            glEnd()
            
            title_pause.draw()
            btn_continue.draw()
            btn_save.draw()
            btn_load.draw()
            btn_menu.draw()
            btn_exit.draw()

            glEnable(GL_DEPTH_TEST)
            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)
            glPopMatrix()

        pygame.display.flip()
        clock.tick(FPS)

    print(f"[game_template] returning result_state={result_state}")
    log_debug(f"[game_template] returning result_state={result_state}")
    pygame.mouse.set_visible(True)
    pygame.event.set_grab(False)
    pygame.event.clear()
    return result_state
