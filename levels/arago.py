import math
import random
import sys
from array import array
from collections import deque

import pygame
from OpenGL.GL import *
from OpenGL.GLU import *
from pygame.locals import *

from core.renderer import draw_cube, draw_floor_tile, draw_u_stairs, draw_computer, draw_collectible, draw_exit_module, draw_creature
from core.physics_engine import (BLOCK_SIZE, WALL_HEIGHT, is_wall, 
                                 has_ramp_below, get_target_y)
from core.ui import Button, Title
import core.save_manager as save_manager

BLOCK_SIZE = 4.0
WALL_HEIGHT = 4.0
INTERACT_DISTANCE = 2.5
TOTAL_ARAGO_ITEMS = 7
ARAGO_MAP_WIDTH = 25
ARAGO_MAP_HEIGHT = 25

LEVEL_COLORS = {
    "Arago": {
        "wall": (0.30, 0.12, 0.08),
        "floor": (0.16, 0.07, 0.05),
        "ceiling": (0.08, 0.03, 0.02),
        "item_body": (0.22, 0.12, 0.08),
        "item_glow": (0.95, 0.92, 0.55),
        "exit_locked": (0.45, 0.08, 0.08),
        "exit_unlocked": (0.15, 0.45, 0.18),
        "creature_body": (0.10, 0.02, 0.02),
        "creature_glow": (0.92, 0.12, 0.08),
    },
    "DEFAULT": {
        "wall": (0.15, 0.20, 0.15),
        "floor": (0.10, 0.10, 0.10),
        "ceiling": (0.05, 0.05, 0.05),
        "item_body": (0.18, 0.18, 0.20),
        "item_glow": (0.90, 0.90, 0.60),
        "exit_locked": (0.35, 0.08, 0.08),
        "exit_unlocked": (0.20, 0.55, 0.25),
        "creature_body": (0.08, 0.08, 0.10),
        "creature_glow": (0.85, 0.20, 0.20),
    },
}

def wrap_hud_lines(font, lines, max_width):
    wrapped_lines = []
    for line in lines:
        if isinstance(line, tuple):
            line_text, line_color = line
        else:
            line_text, line_color = line, (240, 240, 240)

        words = line_text.split()
        if not words:
            wrapped_lines.append(("", line_color))
            continue

        current_line = words[0]
        for word in words[1:]:
            test_line = f"{current_line} {word}"
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                wrapped_lines.append((current_line, line_color))
                current_line = word

        wrapped_lines.append((current_line, line_color))

    return wrapped_lines


def draw_hud(width, height, font, lines):
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    panel_width = min(920, width - 40)
    text_max_width = panel_width - 32
    rendered_lines = wrap_hud_lines(font, lines, text_max_width)
    panel_height = 30 + (len(rendered_lines) * 28)
    pygame.draw.rect(overlay, (8, 10, 16, 185), (20, 20, panel_width, panel_height), border_radius=10)
    pygame.draw.rect(overlay, (220, 140, 40, 225), (20, 20, panel_width, panel_height), width=2, border_radius=10)

    y = 34
    for line, color in rendered_lines:
        text_surface = font.render(line, True, color)
        overlay.blit(text_surface, (36, y))
        y += 28

    overlay_data = pygame.image.tostring(overlay, "RGBA", True)
    texture_id = glGenTextures(1)

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, overlay_data)
    glColor4f(1.0, 1.0, 1.0, 1.0)

    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 1.0)
    glVertex2f(0, 0)
    glTexCoord2f(1.0, 1.0)
    glVertex2f(width, 0)
    glTexCoord2f(1.0, 0.0)
    glVertex2f(width, height)
    glTexCoord2f(0.0, 0.0)
    glVertex2f(0, height)
    glEnd()

    glDisable(GL_TEXTURE_2D)
    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()

    glDeleteTextures([texture_id])


def create_tone_sound(frequencies, duration_ms, volume=0.35, sample_rate=22050):
    sample_count = max(1, int(sample_rate * (duration_ms / 1000.0)))
    fade_samples = max(1, int(sample_count * 0.08))
    samples = array("h")

    for index in range(sample_count):
        t = index / sample_rate
        wave = 0.0
        for frequency in frequencies:
            wave += math.sin(2.0 * math.pi * frequency * t)
        wave /= max(1, len(frequencies))

        envelope = 1.0
        if index < fade_samples:
            envelope = index / fade_samples
        elif index > sample_count - fade_samples:
            envelope = max(0.0, (sample_count - index) / fade_samples)

        samples.append(int(32767 * volume * wave * envelope))

    stereo_samples = array("h")
    for value in samples:
        stereo_samples.append(value)
        stereo_samples.append(value)

    return pygame.mixer.Sound(buffer=stereo_samples.tobytes())


def play_sound(sound_enabled, sounds, name):
    if sound_enabled and name in sounds and sounds[name]:
        sounds[name].play()


def is_wall(x, z, level_map):
    col = int(round(x / BLOCK_SIZE))
    row = int(round(z / BLOCK_SIZE))

    if row < 0 or row >= len(level_map) or col < 0 or col >= len(level_map[0]):
        return True

    return level_map[row][col] == "#"


def init_opengl_fps(width, height):
    glViewport(0, 0, int(width), int(height))
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(75, (width / height), 0.1, 1000.0)
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)
    glDisable(GL_BLEND)


def world_distance(a, b):
    if not a or not b:
        return float("inf")
    return math.dist(a, b)


def world_to_cell(x, z):
    return int(round(z / BLOCK_SIZE)), int(round(x / BLOCK_SIZE))


def cell_to_world(row, col):
    return col * BLOCK_SIZE, row * BLOCK_SIZE


def is_walkable_cell(level_map, row, col):
    if row < 0 or row >= len(level_map) or col < 0 or col >= len(level_map[0]):
        return False
    return level_map[row][col] != "#"


def generate_arago_map(width=ARAGO_MAP_WIDTH, height=ARAGO_MAP_HEIGHT):
    if width % 2 == 0:
        width += 1
    if height % 2 == 0:
        height += 1

    grid = [["#" for _ in range(width)] for _ in range(height)]

    def in_bounds(row, col):
        return 1 <= row < height - 1 and 1 <= col < width - 1

    def carve(row, col):
        grid[row][col] = "."
        directions = [(-2, 0), (2, 0), (0, -2), (0, 2)]
        random.shuffle(directions)

        for delta_row, delta_col in directions:
            next_row = row + delta_row
            next_col = col + delta_col
            if not in_bounds(next_row, next_col):
                continue
            if grid[next_row][next_col] != "#":
                continue

            wall_row = row + (delta_row // 2)
            wall_col = col + (delta_col // 2)
            grid[wall_row][wall_col] = "."
            carve(next_row, next_col)

    carve(1, 1)

    room_attempts = max(4, (width * height) // 120)
    for _ in range(room_attempts):
        room_width = random.choice([3, 5, 5, 7])
        room_height = random.choice([3, 5, 5, 7])

        start_row = random.randrange(1, height - room_height, 2)
        start_col = random.randrange(1, width - room_width, 2)
        end_row = start_row + room_height
        end_col = start_col + room_width

        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                if in_bounds(row, col):
                    grid[row][col] = "."

        possible_doors = []
        for col in range(start_col, end_col):
            if in_bounds(start_row - 1, col):
                possible_doors.append((start_row - 1, col))
            if in_bounds(end_row, col):
                possible_doors.append((end_row, col))
        for row in range(start_row, end_row):
            if in_bounds(row, start_col - 1):
                possible_doors.append((row, start_col - 1))
            if in_bounds(row, end_col):
                possible_doors.append((row, end_col))

        random.shuffle(possible_doors)
        for door_row, door_col in possible_doors[: max(2, len(possible_doors) // 6)]:
            grid[door_row][door_col] = "."

    extra_openings = max(8, (width * height) // 45)
    for _ in range(extra_openings):
        row = random.randrange(1, height - 1)
        col = random.randrange(1, width - 1)
        if row % 2 == 1 and col % 2 == 1:
            continue
        grid[row][col] = "."

    open_cells = [(row, col) for row in range(1, height - 1) for col in range(1, width - 1) if grid[row][col] == "."]
    if len(open_cells) < 3:
        # tenta gerar o mapa novamente até criar um labirinto válido
        return generate_arago_map(width, height)

    def farthest_cell(start_row, start_col):
        queue = deque([(start_row, start_col)])
        distances = {(start_row, start_col): 0}
        farthest = (start_row, start_col)

        while queue:
            row, col = queue.popleft()
            if distances[(row, col)] > distances[farthest]:
                farthest = (row, col)

            for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                next_row = row + delta_row
                next_col = col + delta_col
                if not in_bounds(next_row, next_col):
                    continue
                if grid[next_row][next_col] == "#":
                    continue
                if (next_row, next_col) in distances:
                    continue
                distances[(next_row, next_col)] = distances[(row, col)] + 1
                queue.append((next_row, next_col))

        return farthest, distances

    start_row, start_col = random.choice(open_cells)
    exit_cell, _ = farthest_cell(start_row, start_col)
    player_cell, player_distances = farthest_cell(*exit_cell)

    creature_candidates = [
        cell for cell, distance in player_distances.items()
        if distance >= max(8, (width + height) // 5) and cell not in {player_cell, exit_cell}
    ]
    creature_cell = random.choice(creature_candidates) if creature_candidates else exit_cell

    grid[player_cell[0]][player_cell[1]] = "@"
    grid[exit_cell[0]][exit_cell[1]] = "S"
    if creature_cell not in {player_cell, exit_cell}:
        grid[creature_cell[0]][creature_cell[1]] = "C"

    return ["".join(row) for row in grid]


def find_path(level_map, start_pos, target_pos):
    start_row, start_col = world_to_cell(*start_pos)
    target_row, target_col = world_to_cell(*target_pos)

    if not is_walkable_cell(level_map, start_row, start_col):
        return []
    if not is_walkable_cell(level_map, target_row, target_col):
        return []

    queue = deque([(start_row, start_col)])
    previous = {(start_row, start_col): None}

    while queue:
        row, col = queue.popleft()
        if (row, col) == (target_row, target_col):
            break

        for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            next_row = row + delta_row
            next_col = col + delta_col
            if not is_walkable_cell(level_map, next_row, next_col):
                continue
            if (next_row, next_col) in previous:
                continue
            previous[(next_row, next_col)] = (row, col)
            queue.append((next_row, next_col))

    if (target_row, target_col) not in previous:
        return []

    path = []
    current = (target_row, target_col)
    while current is not None:
        path.append(current)
        current = previous[current]
    path.reverse()
    return path


def get_walkable_neighbors(level_map, row, col):
    neighbors = []
    for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        next_row = row + delta_row
        next_col = col + delta_col
        if is_walkable_cell(level_map, next_row, next_col):
            neighbors.append((next_row, next_col))
    return neighbors


def is_intersection(level_map, row, col):
    return len(get_walkable_neighbors(level_map, row, col)) >= 3


def get_intersection_cutoff_target(level_map, player_position, creature_position, fallback_target):
    path_to_player = find_path(level_map, creature_position, player_position)
    if len(path_to_player) < 4:
        return fallback_target

    best_target = None
    best_score = None
    max_index = min(len(path_to_player), 12)

    for row, col in path_to_player[2:max_index]:
        if not is_intersection(level_map, row, col):
            continue
        candidate_target = cell_to_world(row, col)
        player_to_candidate = find_path(level_map, player_position, candidate_target)
        creature_to_candidate = find_path(level_map, creature_position, candidate_target)
        if not player_to_candidate or not creature_to_candidate:
            continue

        score = len(player_to_candidate) - len(creature_to_candidate)
        if score > 0 and (best_score is None or score > best_score):
            best_target = candidate_target
            best_score = score

    return best_target if best_target else fallback_target


def get_creature_state(items_collected):
    if items_collected <= 0:
        return "Adormecida"
    if items_collected <= 2:
        return "Atenta"
    if items_collected <= 4:
        return "Caçando"
    if items_collected <= 6:
        return "Agressiva"
    return "Furiosa"


def get_creature_speed(items_collected):
    return 0.05 + (items_collected * 0.015)


def get_creature_profile(items_collected):
    state = get_creature_state(items_collected)
    if items_collected <= 0:
        return {
            "state": state,
            "speed": 0.0,
            "awareness_radius": 0.0,
            "path_refresh_ms": 900,
            "spawn_delay_ms": 0,
        }
    if items_collected <= 2:
        return {
            "state": state,
            "speed": 0.07,
            "awareness_radius": BLOCK_SIZE * 4.0,
            "path_refresh_ms": 520,
            "spawn_delay_ms": 2500,
        }
    if items_collected <= 4:
        return {
            "state": state,
            "speed": 0.11,
            "awareness_radius": BLOCK_SIZE * 7.0,
            "path_refresh_ms": 300,
            "spawn_delay_ms": 1000,
        }
    if items_collected <= 6:
        return {
            "state": state,
            "speed": 0.16,
            "awareness_radius": BLOCK_SIZE * 12.0,
            "path_refresh_ms": 180,
            "spawn_delay_ms": 450,
        }
    return {
        "state": state,
        "speed": 0.22,
        "awareness_radius": BLOCK_SIZE * 99.0,
        "path_refresh_ms": 90,
        "spawn_delay_ms": 120,
    }


def get_interaction_prompt(near_item, near_exit, items_collected, exit_unlocked):
    if near_item:
        return "Pressione E para coletar o item"
    if near_exit:
        if exit_unlocked:
            return "Pressione E para evacuar"
        return f"Saida bloqueada. Colete {TOTAL_ARAGO_ITEMS} itens"
    return ""


def format_mission_status_line(label, is_active):
    return f"{label}: {'OK' if is_active else 'PENDENTE'}"


def get_status_color(is_active):
    return (110, 220, 140) if is_active else (255, 170, 90)


def get_collect_progress_color(items_collected):
    if items_collected >= TOTAL_ARAGO_ITEMS:
        return (110, 220, 140)
    if items_collected >= 4:
        return (255, 205, 120)
    return (235, 235, 235)


def choose_random_item_positions(candidate_positions, blocked_positions, total_items):
    valid_positions = []
    for candidate in candidate_positions:
        if any(world_distance(candidate, blocked) < BLOCK_SIZE * 1.5 for blocked in blocked_positions if blocked):
            continue
        valid_positions.append(candidate)

    if len(valid_positions) < total_items:
        valid_positions = candidate_positions[:]

    random.shuffle(valid_positions)
    spacing_steps = [BLOCK_SIZE * 3.0, BLOCK_SIZE * 2.4, BLOCK_SIZE * 1.8, BLOCK_SIZE * 1.4]

    for min_spacing in spacing_steps:
        selected_positions = []
        for candidate in valid_positions:
            if all(world_distance(candidate, selected) >= min_spacing for selected in selected_positions):
                selected_positions.append(candidate)
            if len(selected_positions) == total_items:
                return selected_positions

    return random.sample(valid_positions, total_items)


def start(planet, saved_state=None):
    screen_info = pygame.display.Info()
    screen_width = screen_info.current_w
    screen_height = screen_info.current_h

    pygame.display.set_mode((screen_width, screen_height), DOUBLEBUF | OPENGL)
    init_opengl_fps(screen_width, screen_height)

    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)
    hud_font = pygame.font.SysFont("consolas", 24)
    sound_enabled = True
    sounds = {}

    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=22050, size=-16, channels=2)
        sounds["collect"] = create_tone_sound([660, 880], 180, volume=0.28)
        sounds["wake"] = create_tone_sound([150, 180, 210], 420, volume=0.35)
        sounds["unlock"] = create_tone_sound([520, 660, 820], 320, volume=0.3)
        sounds["blocked"] = create_tone_sound([160, 120], 240, volume=0.3)
        sounds["victory"] = create_tone_sound([440, 554, 660], 520, volume=0.32)
        sounds["danger"] = create_tone_sound([260, 220], 260, volume=0.26)
        sounds["defeat"] = create_tone_sound([220, 165, 110], 700, volume=0.4)
    except pygame.error:
        sound_enabled = False

    clock = pygame.time.Clock()
    fps = 60

    if planet.layout == "random":
        current_map = generate_arago_map()
    else:
        # Se for uma matriz 3D da main (lista contendo andares), pega o andar 0
        if isinstance(planet.layout, list) and isinstance(planet.layout[0], list):
            current_map = planet.layout[0]
        else:
            current_map = planet.layout
    
    level_colors = LEVEL_COLORS.get(planet.name, LEVEL_COLORS["DEFAULT"])

    cam_x, cam_y, cam_z = 0.0, 2.0, 0.0
    yaw = 0.0
    pitch = 0.0

    mouse_sensitivity = 0.15
    move_speed = 0.15
    player_radius = 0.5
    sprint_multiplier = 1.8
    max_stamina = 100.0
    stamina = max_stamina
    stamina_drain_per_second = 26.0
    stamina_recover_per_second = 18.0
    min_stamina_to_sprint = 10.0
    sprint_recover_threshold = 35.0
    stamina_recovery_delay = 1.4
    exhausted = False
    stamina_recovery_timer = 0.0
    sprinting = False

    item_candidate_positions = []
    exit_position = None
    creature_spawn = None

    for row_index, row_string in enumerate(current_map):
        for col_index, char in enumerate(row_string):
            world_pos = (col_index * BLOCK_SIZE, row_index * BLOCK_SIZE)
            
            if char == "@":
                cam_x, cam_z = world_pos
            elif char == "." or char == "I":
                item_candidate_positions.append(world_pos)
            elif char == "S":
                exit_position = world_pos
            elif char == "C":
                creature_spawn = world_pos

    if planet.name == "Arago":
        item_positions = choose_random_item_positions(
            item_candidate_positions,
            [(cam_x, cam_z), exit_position, creature_spawn],
            TOTAL_ARAGO_ITEMS,
        )
    else:
        item_positions = item_candidate_positions[:]

    items_collected = 0
    collected_items = set()
    status_message = "Colete os 7 itens para liberar a saida."
    result_state = "MENU"
    exit_timer = 0

    creature_x, creature_z = creature_spawn if creature_spawn else (cam_x, cam_z)
    creature_yaw = 0.0
    creature_path = []
    next_path_refresh = 0
    creature_state = get_creature_state(items_collected)
    creature_visible = False
    creature_wake_time = 0
    creature_target_position = creature_spawn if creature_spawn else (cam_x, cam_z)
    last_creature_state = creature_state
    next_danger_sound_time = 0
    delta_seconds = 1.0 / fps
    previous_player_position = (cam_x, cam_z)

    running = True

    while running:
        player_position = (cam_x, cam_z)
        remaining_items = [pos for pos in item_positions if pos not in collected_items]
        near_item_position = None
        for item_pos in remaining_items:
            if world_distance(player_position, item_pos) <= INTERACT_DISTANCE:
                near_item_position = item_pos
                break
        near_exit = world_distance(player_position, exit_position) <= INTERACT_DISTANCE
        exit_unlocked = items_collected >= TOTAL_ARAGO_ITEMS
        creature_profile = get_creature_profile(items_collected)
        creature_state = creature_profile["state"]

        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()

            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    running = False
                elif event.key == K_e and planet.name == "Arago":
                    if near_item_position:
                        collected_items.add(near_item_position)
                        items_collected += 1
                        play_sound(sound_enabled, sounds, "collect")
                        creature_profile = get_creature_profile(items_collected)
                        creature_state = creature_profile["state"]
                        creature_visible = True
                        creature_wake_time = pygame.time.get_ticks() + creature_profile["spawn_delay_ms"]
                        play_sound(sound_enabled, sounds, "wake")
                        remaining_count = TOTAL_ARAGO_ITEMS - items_collected
                        if remaining_count > 0:
                            status_message = f"Item coletado. Faltam {remaining_count} para liberar a saida."
                        else:
                            status_message = "Todos os 7 itens foram coletados. A saida foi liberada."
                            play_sound(sound_enabled, sounds, "unlock")
                    elif near_exit:
                        if exit_unlocked:
                            result_state = "VITORIA"
                            status_message = "Evacuacao iniciada. Retornando ao mapa estelar."
                            exit_timer = pygame.time.get_ticks() + 1000
                            play_sound(sound_enabled, sounds, "victory")
                        else:
                            status_message = f"Saida bloqueada. Colete os 7 itens. Atual: {items_collected}/7."
                            play_sound(sound_enabled, sounds, "blocked")
                    else:
                        status_message = "Nenhum item ou saida ao alcance."

        mouse_dx, mouse_dy = pygame.mouse.get_rel()
        yaw += mouse_dx * mouse_sensitivity
        pitch += mouse_dy * mouse_sensitivity
        pitch = max(-89.0, min(89.0, pitch))

        keys = pygame.key.get_pressed()
        yaw_rad = math.radians(yaw)
        front_x = math.sin(yaw_rad)
        front_z = -math.cos(yaw_rad)
        right_x = math.cos(yaw_rad)
        right_z = math.sin(yaw_rad)
        is_moving = keys[K_w] or keys[K_s] or keys[K_a] or keys[K_d]
        wants_to_sprint = keys[K_LSHIFT] or keys[K_RSHIFT]

        if exhausted and stamina >= sprint_recover_threshold:
            exhausted = False

        can_start_sprint = wants_to_sprint and is_moving and not exhausted and stamina > min_stamina_to_sprint
        can_continue_sprint = wants_to_sprint and is_moving and not exhausted and sprinting and stamina > 0.0
        can_sprint = can_continue_sprint or can_start_sprint
        sprinting = can_sprint
        current_move_speed = move_speed * sprint_multiplier if can_sprint else move_speed

        if can_sprint:
            stamina = max(0.0, stamina - (stamina_drain_per_second * delta_seconds))
            if stamina <= 0.0:
                exhausted = True
                stamina_recovery_timer = stamina_recovery_delay
                sprinting = False
        else:
            if stamina_recovery_timer > 0.0:
                stamina_recovery_timer = max(0.0, stamina_recovery_timer - delta_seconds)
            else:
                stamina = min(max_stamina, stamina + (stamina_recover_per_second * delta_seconds))

        next_x = cam_x
        next_z = cam_z

        if keys[K_w]:
            next_x += front_x * current_move_speed
            next_z += front_z * current_move_speed
        if keys[K_s]:
            next_x -= front_x * current_move_speed
            next_z -= front_z * current_move_speed
        if keys[K_a]:
            next_x -= right_x * current_move_speed
            next_z -= right_z * current_move_speed
        if keys[K_d]:
            next_x += right_x * current_move_speed
            next_z += right_z * current_move_speed

        if not is_wall(next_x + (player_radius if next_x > cam_x else -player_radius), cam_z, current_map):
            cam_x = next_x
        if not is_wall(cam_x, next_z + (player_radius if next_z > cam_z else -player_radius), current_map):
            cam_z = next_z

        player_position = (cam_x, cam_z)
        remaining_items = [pos for pos in item_positions if pos not in collected_items]
        near_item_position = None
        for item_pos in remaining_items:
            if world_distance(player_position, item_pos) <= INTERACT_DISTANCE:
                near_item_position = item_pos
                break
        near_exit = world_distance(player_position, exit_position) <= INTERACT_DISTANCE
        exit_unlocked = items_collected >= TOTAL_ARAGO_ITEMS
        creature_profile = get_creature_profile(items_collected)
        creature_state = creature_profile["state"]

        now = pygame.time.get_ticks()
        if creature_state != last_creature_state and items_collected > 0:
            play_sound(sound_enabled, sounds, "danger")
            last_creature_state = creature_state

        if items_collected > 0 and creature_spawn and creature_visible and now >= creature_wake_time:
            player_distance = world_distance(player_position, (creature_x, creature_z))
            should_chase_player = (
                items_collected >= 5 or player_distance <= creature_profile["awareness_radius"]
            )

            if should_chase_player and now >= next_danger_sound_time:
                play_sound(sound_enabled, sounds, "danger")
                next_danger_sound_time = now + max(550, 1300 - (items_collected * 110))

            if should_chase_player:
                player_velocity_x = player_position[0] - previous_player_position[0]
                player_velocity_z = player_position[1] - previous_player_position[1]
                velocity_length = math.hypot(player_velocity_x, player_velocity_z)
                predictive_scale = min(BLOCK_SIZE * 1.25, velocity_length * 10.0)
                predicted_target = (
                    player_position[0] + (player_velocity_x * predictive_scale),
                    player_position[1] + (player_velocity_z * predictive_scale),
                )
                if items_collected >= 4:
                    creature_target_position = get_intersection_cutoff_target(
                        current_map,
                        player_position,
                        (creature_x, creature_z),
                        predicted_target,
                    )
                else:
                    creature_target_position = predicted_target
            else:
                if remaining_items:
                    creature_target_position = min(
                        remaining_items,
                        key=lambda item_pos: world_distance((creature_x, creature_z), item_pos),
                    )
                else:
                    creature_target_position = exit_position if exit_position else player_position

            if now >= next_path_refresh:
                creature_path = find_path(current_map, (creature_x, creature_z), creature_target_position)
                if not creature_path and should_chase_player:
                    creature_path = find_path(current_map, (creature_x, creature_z), player_position)
                    creature_target_position = player_position
                next_path_refresh = now + creature_profile["path_refresh_ms"]

            target_x, target_z = creature_target_position
            if len(creature_path) > 1:
                next_row, next_col = creature_path[1]
                target_x, target_z = cell_to_world(next_row, next_col)

            delta_x = target_x - creature_x
            delta_z = target_z - creature_z
            distance = math.hypot(delta_x, delta_z)
            creature_speed = creature_profile["speed"]

            if distance > 0.01:
                step = min(creature_speed, distance)
                creature_x += (delta_x / distance) * step
                creature_z += (delta_z / distance) * step
                creature_yaw = math.degrees(math.atan2(delta_x, -delta_z))

            if should_chase_player and player_distance <= 1.2:
                status_message = "A criatura alcancou voce."
                if sound_enabled and "defeat" in sounds:
                    sounds["defeat"].play()
                    pygame.time.delay(700)
                result_state = "DERROTA"
                running = False
        elif items_collected > 0 and creature_spawn and creature_visible and now < creature_wake_time:
            status_message = "Voce ouviu algo se movendo pelos corredores."

        previous_player_position = player_position

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glRotatef(pitch, 1, 0, 0)
        glRotatef(yaw, 0, 1, 0)
        glTranslatef(-cam_x, -cam_y, -cam_z)

        pulse_time = pygame.time.get_ticks()

        for row_index, row_string in enumerate(current_map):
            for col_index, char in enumerate(row_string):
                block_x = col_index * BLOCK_SIZE
                block_z = row_index * BLOCK_SIZE

                # desenha o chão
                draw_floor_tile(block_x, 0, block_z, BLOCK_SIZE, color=level_colors["floor"])
                
                # desenha o teto
                draw_floor_tile(block_x, WALL_HEIGHT, block_z, BLOCK_SIZE, color=level_colors["ceiling"])

                # desenha a parede
                if char == "#" or char == "P": # Suporta o padrão antigo ou o novo 'P'
                    draw_cube(block_x, 0, block_z, BLOCK_SIZE, WALL_HEIGHT, color=level_colors["wall"])

                elif char == "S":
                    draw_exit_module(
                        block_x,
                        0,
                        block_z,
                        BLOCK_SIZE * 0.82,
                        level_colors["exit_locked"],
                        level_colors["exit_unlocked"],
                        exit_unlocked,
                        pulse_time,
                    )

        for item_x, item_z in item_positions:
            if (item_x, item_z) not in collected_items:
                draw_collectible(
                    item_x,
                    0,
                    item_z,
                    BLOCK_SIZE,
                    level_colors["item_body"],
                    level_colors["item_glow"],
                    pulse_time,
                )

        if items_collected > 0 and creature_spawn and creature_visible and now >= creature_wake_time:
            draw_creature(
                creature_x,
                0,
                creature_z,
                creature_yaw,
                level_colors["creature_body"],
                level_colors["creature_glow"],
                pulse_time,
            )

        interaction_prompt = get_interaction_prompt(near_item_position is not None, near_exit, items_collected, exit_unlocked)

        hud_lines = [(f"Planeta: {planet.name}", (235, 235, 235))]

        if planet.name == "Arago":
            current_objective = "Coletar os 7 itens" if not exit_unlocked else "Alcancar a saida"
            hud_lines.append((f"Objetivo atual: {current_objective}", (255, 215, 120)))
            hud_lines.append((f"Itens coletados: {items_collected}/{TOTAL_ARAGO_ITEMS}", get_collect_progress_color(items_collected)))
            hud_lines.append((format_mission_status_line("Saida", exit_unlocked), get_status_color(exit_unlocked)))
            stamina_color = (255, 95, 95) if exhausted else get_status_color(stamina > 35.0)
            hud_lines.append((f"Estamina: {int(stamina)}/{int(max_stamina)}", stamina_color))
            hud_lines.append(("Shift para correr", (190, 220, 255)))
            if stamina_recovery_timer > 0.0:
                hud_lines.append(("Exausto: recuperando folego...", (255, 95, 95)))
            elif exhausted:
                hud_lines.append(("Exausto: espere a estamina recarregar.", (255, 95, 95)))
            if items_collected <= 0:
                creature_line = "Criatura: adormecida"
                creature_color = (180, 180, 180)
            elif creature_visible and now < creature_wake_time:
                creature_line = f"Criatura: {creature_state} (despertando)"
                creature_color = (255, 185, 120)
            elif creature_visible:
                creature_line = f"Criatura: {creature_state}"
                creature_color = (255, 140, 140)
            else:
                creature_line = f"Criatura: {creature_state}"
                creature_color = (200, 180, 180)
            hud_lines.append((creature_line, creature_color))
            hud_lines.append((f"Agressividade: nivel {min(items_collected + 1, TOTAL_ARAGO_ITEMS)}", (255, 170, 90)))
            hud_lines.append((status_message, (240, 240, 240)))

            if interaction_prompt:
                hud_lines.append((interaction_prompt, (255, 205, 120)))
            else:
                if not exit_unlocked:
                    hud_lines.append(("Explore os corredores e encontre os itens restantes.", (255, 205, 120)))
                else:
                    hud_lines.append(("Corra para o modulo verde de saida.", (140, 235, 160)))
        else:
            hud_lines.append(("ESC para voltar.", (235, 235, 235)))

        draw_hud(screen_width, screen_height, hud_font, hud_lines)

        pygame.display.flip()
        delta_seconds = clock.tick(fps) / 1000.0

        if result_state == "VITORIA" and pygame.time.get_ticks() >= exit_timer:
            running = False

    return result_state


if __name__ == "__main__":
    pygame.init()
    start("Arago")