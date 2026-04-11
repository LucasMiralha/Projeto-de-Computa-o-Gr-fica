import math
import sys
from array import array
from collections import deque

import pygame
from OpenGL.GL import *
from OpenGL.GLU import *
from pygame.locals import *

# ==========================================
# DADOS DAS FASES (LEVEL DESIGN)
# ==========================================
# '#' = Parede, '.' = Chao livre, 'P' = Spawn
# 'E' = Energia, 'R' = Refrigeracao, 'T' = Terminal
# 'D' = Porta da saida, 'S' = Modulo de saida
# 'H' = Area de baixa exposicao, 'V' = Zona de vapor
# 'M' = Gatilho principal da criatura
LEVELS = {
    "Tau Ceti IV": [
        "##########",
        "#P.......#",
        "####..####",
        "#........#",
        "#.######.#",
        "#......C.#",
        "##########",
    ],
    "Arago": [
        "#############",
        "#P....M...S##",
        "#.###.#.#D.##",
        "#..E..#....##",
        "##.#.###.#.##",
        "#..R..H.T..##",
        "#....V.....##",
        "#############",
    ],
    "DEFAULT": [
        "######",
        "#P...#",
        "######",
    ],
}

LEVEL_CONFIGS = {
    "Arago": {
        "title": "Arago: Eco de Pressao",
        "mission": "Ative energia, refrigeracao e autorizacao para liberar a saida.",
        "hint": "Tudo que voce liga chama atencao. Use o som a seu favor.",
        "wall_color": (0.30, 0.12, 0.08),
        "floor_color": (0.16, 0.07, 0.05),
        "ceiling_color": (0.08, 0.03, 0.02),
        "energy_color": (1.00, 0.78, 0.22),
        "cooling_color": (0.34, 0.80, 1.00),
        "terminal_color": (1.00, 0.42, 0.10),
        "exit_color": (0.60, 1.00, 0.60),
        "door_locked_color": (0.45, 0.08, 0.08),
        "door_open_color": (0.15, 0.45, 0.18),
        "hideout_color": (0.32, 0.32, 0.38),
        "steam_color": (0.72, 0.72, 0.72),
        "threat_color": (0.85, 0.12, 0.08),
    },
    "DEFAULT": {
        "title": "Default",
        "mission": "Explore a area.",
        "hint": "Use WASD para mover e ESC para voltar.",
        "wall_color": (0.15, 0.20, 0.15),
        "floor_color": (0.10, 0.10, 0.10),
        "ceiling_color": (0.05, 0.05, 0.05),
        "energy_color": (1.00, 0.78, 0.22),
        "cooling_color": (0.34, 0.80, 1.00),
        "terminal_color": (0.20, 0.80, 1.00),
        "exit_color": (0.60, 1.00, 0.60),
        "door_locked_color": (0.45, 0.08, 0.08),
        "door_open_color": (0.15, 0.45, 0.18),
        "hideout_color": (0.32, 0.32, 0.38),
        "steam_color": (0.72, 0.72, 0.72),
        "threat_color": (0.85, 0.12, 0.08),
    },
}

BLOCK_SIZE = 4.0
WALL_HEIGHT = 4.0


def draw_cube(x, y, z, size, height, color):
    half = size / 2.0

    glBegin(GL_QUADS)
    glColor3f(*color)

    glVertex3f(x - half, y, z + half)
    glVertex3f(x + half, y, z + half)
    glVertex3f(x + half, y + height, z + half)
    glVertex3f(x - half, y + height, z + half)

    glVertex3f(x - half, y, z - half)
    glVertex3f(x - half, y + height, z - half)
    glVertex3f(x + half, y + height, z - half)
    glVertex3f(x + half, y, z - half)

    glVertex3f(x - half, y, z - half)
    glVertex3f(x - half, y, z + half)
    glVertex3f(x - half, y + height, z + half)
    glVertex3f(x - half, y + height, z - half)

    glVertex3f(x + half, y, z - half)
    glVertex3f(x + half, y + height, z - half)
    glVertex3f(x + half, y + height, z + half)
    glVertex3f(x + half, y, z + half)
    glEnd()


def draw_floor_and_ceiling(level_map, floor_color, ceiling_color):
    rows = len(level_map)
    cols = len(level_map[0])

    width = cols * BLOCK_SIZE
    depth = rows * BLOCK_SIZE
    start_x = -BLOCK_SIZE / 2.0
    start_z = -BLOCK_SIZE / 2.0

    glBegin(GL_QUADS)
    glColor3f(*floor_color)
    glVertex3f(start_x, 0.0, start_z)
    glVertex3f(start_x + width, 0.0, start_z)
    glVertex3f(start_x + width, 0.0, start_z + depth)
    glVertex3f(start_x, 0.0, start_z + depth)

    glColor3f(*ceiling_color)
    glVertex3f(start_x, WALL_HEIGHT, start_z)
    glVertex3f(start_x, WALL_HEIGHT, start_z + depth)
    glVertex3f(start_x + width, WALL_HEIGHT, start_z + depth)
    glVertex3f(start_x + width, WALL_HEIGHT, start_z)
    glEnd()


def draw_panel(x, y, z, size, color):
    half = size / 2.0
    height = WALL_HEIGHT * 0.75

    glBegin(GL_QUADS)
    glColor3f(0.12, 0.12, 0.12)
    glVertex3f(x - half, y, z + half)
    glVertex3f(x + half, y, z + half)
    glVertex3f(x + half, y + height, z + half)
    glVertex3f(x - half, y + height, z + half)

    glVertex3f(x - half, y, z - half)
    glVertex3f(x - half, y + height, z - half)
    glVertex3f(x + half, y + height, z - half)
    glVertex3f(x + half, y, z - half)

    glVertex3f(x - half, y, z - half)
    glVertex3f(x - half, y, z + half)
    glVertex3f(x - half, y + height, z + half)
    glVertex3f(x - half, y + height, z - half)

    glVertex3f(x + half, y, z - half)
    glVertex3f(x + half, y + height, z - half)
    glVertex3f(x + half, y + height, z + half)
    glVertex3f(x + half, y, z + half)
    glEnd()

    screen_height = height * 0.55
    screen_width = size * 0.7
    glBegin(GL_QUADS)
    glColor3f(*color)
    glVertex3f(x - screen_width / 2, y + 0.9, z + half + 0.02)
    glVertex3f(x + screen_width / 2, y + 0.9, z + half + 0.02)
    glVertex3f(x + screen_width / 2, y + 0.9 + screen_height, z + half + 0.02)
    glVertex3f(x - screen_width / 2, y + 0.9 + screen_height, z + half + 0.02)
    glEnd()


def draw_beacon(x, y, z, color, pulse_time, height=4.6):
    pulse = 0.75 + ((math.sin(pulse_time * 0.006) + 1.0) * 0.12)
    beacon_color = tuple(min(1.0, channel * pulse) for channel in color)
    glBegin(GL_QUADS)
    glColor3f(*beacon_color)
    width = 0.18
    glVertex3f(x - width, y, z + width)
    glVertex3f(x + width, y, z + width)
    glVertex3f(x + width, y + height, z + width)
    glVertex3f(x - width, y + height, z + width)
    glEnd()


def draw_pickup(x, y, z, size, color, pulse_time):
    half = size / 2.0
    bob = math.sin(pulse_time * 0.004) * 0.18
    glow = 0.75 + ((math.sin(pulse_time * 0.006) + 1.0) * 0.125)
    glow_color = tuple(min(1.0, channel * glow) for channel in color)

    glBegin(GL_QUADS)
    glColor3f(*glow_color)

    glVertex3f(x - half, y + bob, z + half)
    glVertex3f(x + half, y + bob, z + half)
    glVertex3f(x + half, y + size + bob, z + half)
    glVertex3f(x - half, y + size + bob, z + half)

    glVertex3f(x - half, y + bob, z - half)
    glVertex3f(x - half, y + size + bob, z - half)
    glVertex3f(x + half, y + size + bob, z - half)
    glVertex3f(x + half, y + bob, z - half)

    glVertex3f(x - half, y + bob, z - half)
    glVertex3f(x - half, y + bob, z + half)
    glVertex3f(x - half, y + size + bob, z + half)
    glVertex3f(x - half, y + size + bob, z - half)

    glVertex3f(x + half, y + bob, z - half)
    glVertex3f(x + half, y + size + bob, z - half)
    glVertex3f(x + half, y + size + bob, z + half)
    glVertex3f(x + half, y + bob, z + half)

    glVertex3f(x - half, y + size + bob, z - half)
    glVertex3f(x - half, y + size + bob, z + half)
    glVertex3f(x + half, y + size + bob, z + half)
    glVertex3f(x + half, y + size + bob, z - half)
    glEnd()


def draw_creature(x, y, z, pulse_time):
    body_height = 3.2 + math.sin(pulse_time * 0.004) * 0.18
    body_size = BLOCK_SIZE * 0.34
    head_size = body_size * 0.62

    draw_cube(x, y, z, body_size, body_height, (0.10, 0.02, 0.02))
    draw_cube(x, y + body_height * 0.72, z, head_size, body_height * 0.42, (0.18, 0.03, 0.03))

    glBegin(GL_QUADS)
    glColor3f(0.95, 0.10, 0.08)
    eye_y = y + body_height * 0.98
    eye_z = z + head_size / 2 + 0.03
    eye_offset = head_size * 0.18
    eye_size = 0.12
    for eye_x in (x - eye_offset, x + eye_offset):
        glVertex3f(eye_x - eye_size, eye_y - eye_size, eye_z)
        glVertex3f(eye_x + eye_size, eye_y - eye_size, eye_z)
        glVertex3f(eye_x + eye_size, eye_y + eye_size, eye_z)
        glVertex3f(eye_x - eye_size, eye_y + eye_size, eye_z)
    glEnd()


def draw_arrow_marker(x, y, z, color, pulse_time):
    bob = math.sin(pulse_time * 0.005) * 0.15
    glBegin(GL_TRIANGLES)
    glColor3f(*color)
    glVertex3f(x, y + 2.5 + bob, z)
    glVertex3f(x - 0.35, y + 1.9 + bob, z)
    glVertex3f(x + 0.35, y + 1.9 + bob, z)
    glEnd()


def draw_hud_lines(screen, font, lines):
    y = 20
    for text in lines:
        surface = font.render(text, True, (230, 230, 230))
        screen.blit(surface, (20, y))
        y += surface.get_height() + 8


def draw_center_message(screen, title_font, body_font, title, lines):
    title_surface = title_font.render(title, True, (255, 240, 220))
    panel_width = max(760, title_surface.get_width() + 80)
    panel_height = 140 + len(lines) * 38
    panel_x = (screen.get_width() - panel_width) // 2
    panel_y = (screen.get_height() - panel_height) // 2

    overlay = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
    overlay.fill((8, 6, 6, 215))
    screen.blit(overlay, (panel_x, panel_y))

    screen.blit(title_surface, (panel_x + 32, panel_y + 24))
    current_y = panel_y + 82
    for line in lines:
        body_surface = body_font.render(line, True, (235, 235, 235))
        screen.blit(body_surface, (panel_x + 32, current_y))
        current_y += 36


def draw_screen_overlay(width, height, alpha, color):
    if alpha <= 0:
        return

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glDisable(GL_TEXTURE_2D)
    glColor4f(color[0], color[1], color[2], alpha)

    glBegin(GL_QUADS)
    glVertex2f(0, 0)
    glVertex2f(width, 0)
    glVertex2f(width, height)
    glVertex2f(0, height)
    glEnd()

    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()


def objective_progress_text(energy_active, cooling_active, terminal_authorized):
    parts = [
        f"Energia {'OK' if energy_active else 'PENDENTE'}",
        f"Refrigeracao {'OK' if cooling_active else 'PENDENTE'}",
        f"Autorizacao {'OK' if terminal_authorized else 'PENDENTE'}",
    ]
    return " | ".join(parts)


def create_tone_sound(frequency, duration_ms, volume=0.25, sample_rate=22050):
    sample_count = int(sample_rate * (duration_ms / 1000.0))
    fade_samples = max(1, int(sample_count * 0.08))
    samples = array("h")

    for index in range(sample_count):
        amplitude = math.sin(2.0 * math.pi * frequency * (index / sample_rate))
        envelope = 1.0
        if index < fade_samples:
            envelope = index / fade_samples
        elif index > sample_count - fade_samples:
            envelope = max(0.0, (sample_count - index) / fade_samples)
        value = int(32767 * volume * amplitude * envelope)
        samples.append(value)

    stereo_samples = array("h")
    for value in samples:
        stereo_samples.append(value)
        stereo_samples.append(value)
    return pygame.mixer.Sound(buffer=stereo_samples.tobytes())


def map_cell_from_world(x, z):
    return int(round(z / BLOCK_SIZE)), int(round(x / BLOCK_SIZE))


def world_from_cell(row, col):
    return col * BLOCK_SIZE, row * BLOCK_SIZE


def is_blocking_cell(cell, door_open=False):
    if cell == "#":
        return True
    if cell == "D" and not door_open:
        return True
    return False


def is_wall(x, z, level_map, door_open=False):
    row, col = map_cell_from_world(x, z)

    if row < 0 or row >= len(level_map) or col < 0 or col >= len(level_map[0]):
        return True

    cell = level_map[row][col]
    return is_blocking_cell(cell, door_open)


def find_path(level_map, start_row, start_col, goal_row, goal_col, door_open=False):
    rows = len(level_map)
    cols = len(level_map[0])

    if not (0 <= start_row < rows and 0 <= start_col < cols):
        return []
    if not (0 <= goal_row < rows and 0 <= goal_col < cols):
        return []
    if is_blocking_cell(level_map[goal_row][goal_col], door_open):
        return []

    queue = deque([(start_row, start_col)])
    came_from = {(start_row, start_col): None}

    while queue:
        row, col = queue.popleft()
        if (row, col) == (goal_row, goal_col):
            break

        for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            next_row = row + delta_row
            next_col = col + delta_col
            if not (0 <= next_row < rows and 0 <= next_col < cols):
                continue
            if (next_row, next_col) in came_from:
                continue
            if is_blocking_cell(level_map[next_row][next_col], door_open):
                continue

            came_from[(next_row, next_col)] = (row, col)
            queue.append((next_row, next_col))

    if (goal_row, goal_col) not in came_from:
        return []

    path = []
    current = (goal_row, goal_col)
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path


def has_line_of_sight(level_map, start_x, start_z, end_x, end_z, door_open=False, samples=24):
    for step in range(1, samples):
        t = step / samples
        test_x = start_x + (end_x - start_x) * t
        test_z = start_z + (end_z - start_z) * t
        row, col = map_cell_from_world(test_x, test_z)
        if row < 0 or row >= len(level_map) or col < 0 or col >= len(level_map[0]):
            return False
        if is_blocking_cell(level_map[row][col], door_open):
            return False
    return True


def init_opengl_fps(width, height):
    glViewport(0, 0, int(width), int(height))
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(75, (width / height), 0.1, 1000.0)
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)
    glDisable(GL_BLEND)


def start(planet_name):
    screen_info = pygame.display.Info()
    screen_width = screen_info.current_w
    screen_height = screen_info.current_h

    pygame.display.set_mode((screen_width, screen_height), DOUBLEBUF | OPENGL)
    screen = pygame.display.get_surface()

    init_opengl_fps(screen_width, screen_height)

    sound_enabled = True
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=22050, size=-16, channels=2)
    except pygame.error:
        sound_enabled = False

    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)

    clock = pygame.time.Clock()
    fps = 60

    current_map = LEVELS.get(planet_name, LEVELS["DEFAULT"])
    level_config = LEVEL_CONFIGS.get(planet_name, LEVEL_CONFIGS["DEFAULT"])
    hud_font = pygame.font.SysFont("Arial", 24, bold=True)
    small_font = pygame.font.SysFont("Arial", 20, bold=True)
    title_font = pygame.font.SysFont("Arial", 34, bold=True)

    cam_x, cam_y, cam_z = 0.0, 2.0, 0.0
    yaw = 0.0
    pitch = 0.0

    mouse_sensitivity = 0.15
    move_speed = 0.17
    player_radius = 0.5

    energy_pos = None
    cooling_pos = None
    terminal_pos = None
    exit_pos = None
    hideout_positions = []
    steam_positions = []
    menace_positions = []

    for row_index, row_string in enumerate(current_map):
        for col_index, char in enumerate(row_string):
            world_x = col_index * BLOCK_SIZE
            world_z = row_index * BLOCK_SIZE

            if char == "P":
                cam_x = world_x
                cam_z = world_z
            elif char == "E":
                energy_pos = (world_x, world_z)
            elif char == "R":
                cooling_pos = (world_x, world_z)
            elif char == "T":
                terminal_pos = (world_x, world_z)
            elif char == "S":
                exit_pos = (world_x, world_z)
            elif char == "H":
                hideout_positions.append((world_x, world_z))
            elif char == "V":
                steam_positions.append((world_x, world_z))
            elif char == "M":
                menace_positions.append((world_x, world_z))

    energy_active = False
    cooling_active = False
    terminal_authorized = False
    menace_triggered = False
    hideout_message_seen = False
    result_state = "MENU"
    ending_started_at = 0

    creature_state = "Adormecida"
    status_message = "Instalacao geotermica comprometida. Saida bloqueada."
    interact_message = ""
    current_objective = "Restaure a energia auxiliar."
    creature_visible = False
    creature_x = menace_positions[0][0] if menace_positions else cam_x
    creature_z = menace_positions[0][1] if menace_positions else cam_z
    creature_target_x = creature_x
    creature_target_z = creature_z
    creature_speed = 0.08
    chase_until = 0
    creature_cooldown_until = 0
    creature_path = []
    next_path_refresh_at = 0
    creature_last_known_x = creature_x
    creature_last_known_z = creature_z
    creature_last_seen_at = 0
    noise_until = 0
    noise_source_x = creature_x
    noise_source_z = creature_z
    alert_message = ""
    alert_until = 0
    overlay_alpha = 0.0
    overlay_color = (0.0, 0.0, 0.0)
    last_sound_event = ""
    show_intro = planet_name == "Arago"
    guidance_until = pygame.time.get_ticks() + 16000
    first_manifest_done = False

    sounds = {}
    if sound_enabled:
        try:
            sounds = {
                "noise": create_tone_sound(140, 220, 0.22),
                "seen": create_tone_sound(220, 180, 0.20),
                "chase": create_tone_sound(90, 420, 0.28),
                "danger": create_tone_sound(180, 120, 0.16),
            }
        except pygame.error:
            sound_enabled = False
            sounds = {}

    def play_sound(name):
        nonlocal last_sound_event
        if not sound_enabled:
            return
        sound = sounds.get(name)
        if sound is None:
            return
        if last_sound_event == name and name in {"seen", "danger"}:
            return
        sound.play()
        last_sound_event = name

    def door_open():
        return energy_active and cooling_active and terminal_authorized

    def objective_label():
        if not energy_active:
            return "Objetivo: ativar energia auxiliar"
        if not cooling_active:
            return "Objetivo: estabilizar a refrigeracao"
        if not terminal_authorized:
            return "Objetivo: autorizar o modulo de saida"
        return "Objetivo: escapar pelo modulo de saida"

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()

            if event.type == KEYDOWN:
                if show_intro:
                    if event.key in (K_SPACE, K_RETURN, K_e, K_w, K_a, K_s, K_d):
                        show_intro = False
                        guidance_until = pygame.time.get_ticks() + 20000
                    elif event.key == K_ESCAPE:
                        running = False
                    continue

                if event.key == K_ESCAPE:
                    running = False

                if event.key == K_e:
                    if interact_message.startswith("Pressione E para restaurar"):
                        energy_active = True
                        creature_state = "Investigando"
                        creature_visible = True
                        creature_target_x, creature_target_z = energy_pos
                        creature_cooldown_until = pygame.time.get_ticks() + 3200
                        noise_until = pygame.time.get_ticks() + 3600
                        noise_source_x, noise_source_z = energy_pos
                        alert_message = "O ruido atravessou a instalacao."
                        alert_until = pygame.time.get_ticks() + 1800
                        play_sound("noise")
                        current_objective = objective_label()
                        status_message = "Energia auxiliar online. Algo respondeu ao ruido."
                        guidance_until = pygame.time.get_ticks() + 8000
                    elif interact_message.startswith("Pressione E para estabilizar"):
                        cooling_active = True
                        creature_state = "Presenca"
                        creature_visible = True
                        creature_target_x, creature_target_z = cooling_pos
                        creature_cooldown_until = pygame.time.get_ticks() + 4200
                        noise_until = pygame.time.get_ticks() + 4500
                        noise_source_x, noise_source_z = cooling_pos
                        alert_message = "Tubulacoes gritaram. Algo veio investigar."
                        alert_until = pygame.time.get_ticks() + 1800
                        play_sound("noise")
                        current_objective = objective_label()
                        status_message = "Refrigeracao estabilizada. Os corredores ficaram inquietos."
                        guidance_until = pygame.time.get_ticks() + 8000
                    elif interact_message.startswith("Pressione E para autorizar"):
                        terminal_authorized = True
                        creature_state = "Investida"
                        creature_visible = True
                        creature_target_x = cam_x
                        creature_target_z = cam_z
                        chase_until = pygame.time.get_ticks() + 6500
                        creature_last_known_x = cam_x
                        creature_last_known_z = cam_z
                        creature_last_seen_at = pygame.time.get_ticks()
                        alert_message = "O Escutador ouviu voce claramente."
                        alert_until = pygame.time.get_ticks() + 2200
                        play_sound("chase")
                        current_objective = objective_label()
                        status_message = "Autorizacao confirmada. A criatura agora sabe onde voce esta."
                        guidance_until = pygame.time.get_ticks() + 9000
                    elif interact_message.startswith("Pressione E para evacuar"):
                        result_state = "VITORIA"
                        ending_started_at = pygame.time.get_ticks()
                        status_message = "Modulo de saida acionado. Evacuacao em andamento."

        mouse_dx, mouse_dy = pygame.mouse.get_rel()
        if not show_intro:
            yaw += mouse_dx * mouse_sensitivity
            pitch += mouse_dy * mouse_sensitivity
        pitch = max(-89.0, min(89.0, pitch))

        keys = pygame.key.get_pressed()
        yaw_rad = math.radians(yaw)
        front_x = math.sin(yaw_rad)
        front_z = -math.cos(yaw_rad)
        right_x = math.cos(yaw_rad)
        right_z = math.sin(yaw_rad)

        next_x = cam_x
        next_z = cam_z

        if not show_intro and keys[K_w]:
            next_x += front_x * move_speed
            next_z += front_z * move_speed
        if not show_intro and keys[K_s]:
            next_x -= front_x * move_speed
            next_z -= front_z * move_speed
        if not show_intro and keys[K_a]:
            next_x -= right_x * move_speed
            next_z -= right_z * move_speed
        if not show_intro and keys[K_d]:
            next_x += right_x * move_speed
            next_z += right_z * move_speed

        if not is_wall(
            next_x + (player_radius if next_x > cam_x else -player_radius),
            cam_z,
            current_map,
            door_open(),
        ):
            cam_x = next_x

        if not is_wall(
            cam_x,
            next_z + (player_radius if next_z > cam_z else -player_radius),
            current_map,
            door_open(),
        ):
            cam_z = next_z

        interact_radius = BLOCK_SIZE * 1.25
        near_energy = energy_pos and math.hypot(cam_x - energy_pos[0], cam_z - energy_pos[1]) <= interact_radius
        near_cooling = cooling_pos and math.hypot(cam_x - cooling_pos[0], cam_z - cooling_pos[1]) <= interact_radius
        near_terminal = terminal_pos and math.hypot(cam_x - terminal_pos[0], cam_z - terminal_pos[1]) <= interact_radius
        near_exit = exit_pos and math.hypot(cam_x - exit_pos[0], cam_z - exit_pos[1]) <= interact_radius
        in_hideout = any(math.hypot(cam_x - hx, cam_z - hz) <= BLOCK_SIZE * 0.9 for hx, hz in hideout_positions)
        in_steam = any(math.hypot(cam_x - vx, cam_z - vz) <= BLOCK_SIZE * 0.9 for vx, vz in steam_positions)
        in_menace_zone = any(math.hypot(cam_x - mx, cam_z - mz) <= BLOCK_SIZE * 0.9 for mx, mz in menace_positions)

        if in_menace_zone and not menace_triggered:
            menace_triggered = True
            if creature_state == "Adormecida":
                creature_state = "Investigando"
            creature_visible = True
            if menace_positions:
                creature_target_x, creature_target_z = menace_positions[0]
                noise_source_x, noise_source_z = menace_positions[0]
                noise_until = pygame.time.get_ticks() + 1800
            alert_message = "Algo acordou nas profundezas de Arago."
            alert_until = pygame.time.get_ticks() + 1800
            play_sound("danger")
            status_message = "Voce ouviu algo grande se mover dentro das tubulacoes."

        if (
            planet_name == "Arago"
            and not first_manifest_done
            and not show_intro
            and menace_positions
            and math.hypot(cam_x - menace_positions[0][0], cam_z - menace_positions[0][1]) <= BLOCK_SIZE * 2.8
        ):
            first_manifest_done = True
            creature_visible = True
            if menace_positions:
                creature_x, creature_z = menace_positions[0]
                creature_target_x, creature_target_z = menace_positions[0]
            creature_state = "Presenca"
            alert_message = "O Escutador atravessou o corredor a sua frente."
            alert_until = pygame.time.get_ticks() + 2600
            play_sound("danger")
            status_message = "Voce nao esta sozinho em Arago."
            guidance_until = pygame.time.get_ticks() + 6000

        if in_hideout and not hideout_message_seen:
            hideout_message_seen = True
            status_message = "Area de baixa exposicao sonora. Bom lugar para recuperar o folego."

        if in_steam:
            status_message = "Vapor superaquecido. Sua silhueta fica mais facil de rastrear."

        now = pygame.time.get_ticks()
        player_distance_to_creature = math.hypot(cam_x - creature_x, cam_z - creature_z) if creature_visible else 9999
        can_see_player = False
        if creature_visible:
            can_see_player = (
                player_distance_to_creature <= BLOCK_SIZE * 5.2
                and has_line_of_sight(current_map, creature_x, creature_z, cam_x, cam_z, door_open())
            )

        if can_see_player:
            creature_last_known_x = cam_x
            creature_last_known_z = cam_z
            creature_last_seen_at = now
            if creature_state == "Adormecida":
                creature_state = "Investigando"
            alert_message = "O Escutador viu voce."
            alert_until = max(alert_until, now + 700)
            play_sound("seen")

        if chase_until and now <= chase_until:
            creature_state = "Investida"
            if can_see_player or now - creature_last_seen_at < 1600:
                creature_target_x = creature_last_known_x
                creature_target_z = creature_last_known_z
            creature_speed = 0.135
            if last_sound_event != "chase":
                play_sound("chase")
        elif can_see_player:
            creature_state = "Presenca"
            creature_target_x = creature_last_known_x
            creature_target_z = creature_last_known_z
            creature_speed = 0.095
        elif noise_until and now <= noise_until:
            creature_state = "Investigando"
            creature_target_x = noise_source_x
            creature_target_z = noise_source_z
            creature_speed = 0.085
        elif creature_visible and now <= creature_cooldown_until:
            creature_speed = 0.08
            if creature_state == "Adormecida":
                creature_state = "Investigando"
        elif creature_visible:
            creature_speed = 0.06
            if now - creature_last_seen_at < 2600:
                creature_target_x = creature_last_known_x
                creature_target_z = creature_last_known_z
                if creature_state == "Investida":
                    creature_state = "Presenca"
            else:
                if menace_positions:
                    creature_target_x, creature_target_z = menace_positions[0]
                if creature_state != "Adormecida":
                    creature_state = "Investigando"

        if creature_visible:
            creature_row, creature_col = map_cell_from_world(creature_x, creature_z)
            target_row, target_col = map_cell_from_world(creature_target_x, creature_target_z)
            if now >= next_path_refresh_at or not creature_path:
                creature_path = find_path(
                    current_map,
                    creature_row,
                    creature_col,
                    target_row,
                    target_col,
                    door_open(),
                )
                next_path_refresh_at = now + 350

            if len(creature_path) > 1:
                next_row, next_col = creature_path[1]
                waypoint_x, waypoint_z = world_from_cell(next_row, next_col)
            else:
                waypoint_x, waypoint_z = creature_target_x, creature_target_z

            delta_x = waypoint_x - creature_x
            delta_z = waypoint_z - creature_z
            distance_to_waypoint = math.hypot(delta_x, delta_z)
            if distance_to_waypoint > 0.05:
                step = min(creature_speed, distance_to_waypoint)
                creature_x += (delta_x / distance_to_waypoint) * step
                creature_z += (delta_z / distance_to_waypoint) * step
            elif len(creature_path) > 1:
                creature_path = creature_path[1:]

            player_distance = math.hypot(cam_x - creature_x, cam_z - creature_z)
            if player_distance < BLOCK_SIZE * 0.75 and now > ending_started_at and not in_hideout:
                status_message = "O Escutador encontrou voce. Recuando para o mapa estelar."
                running = False

            distance_to_target = math.hypot(creature_target_x - creature_x, creature_target_z - creature_z)
            if creature_state == "Investigando" and distance_to_target < BLOCK_SIZE * 0.5 and now > noise_until:
                creature_state = "Presenca"
            if in_hideout and creature_state == "Presenca":
                creature_target_x = creature_x
                creature_target_z = creature_z
                status_message = "Voce escuta a criatura rondando do lado de fora."

        if keys[K_w] or keys[K_a] or keys[K_s] or keys[K_d]:
            if creature_visible and not in_hideout and player_distance_to_creature <= BLOCK_SIZE * 3.2:
                noise_source_x = cam_x
                noise_source_z = cam_z
                noise_until = max(noise_until, now + 450)

        if now <= alert_until:
            pulse = 0.5 + 0.5 * math.sin(now * 0.02)
            if creature_state == "Investida":
                overlay_color = (0.35, 0.02, 0.02)
                overlay_alpha = 0.16 + pulse * 0.10
            elif can_see_player:
                overlay_color = (0.22, 0.04, 0.04)
                overlay_alpha = 0.10 + pulse * 0.06
            else:
                overlay_color = (0.10, 0.08, 0.02)
                overlay_alpha = 0.05 + pulse * 0.04
        else:
            overlay_alpha = 0.0
            if last_sound_event in {"seen", "danger"}:
                last_sound_event = ""

        interact_message = ""
        if near_energy and not energy_active:
            interact_message = "Pressione E para restaurar energia auxiliar"
        elif near_cooling and energy_active and not cooling_active:
            interact_message = "Pressione E para estabilizar a refrigeracao"
        elif near_cooling and not energy_active:
            interact_message = "Refrigeracao offline. Primeiro restaure a energia"
        elif near_terminal and energy_active and cooling_active and not terminal_authorized:
            interact_message = "Pressione E para autorizar o modulo de saida"
        elif near_terminal and not terminal_authorized:
            interact_message = "Autorizacao negada: sistemas incompletos"
        elif near_exit and door_open():
            interact_message = "Pressione E para evacuar"
        elif near_exit and not door_open():
            interact_message = "Modulo de saida bloqueado"

        current_objective = objective_label()
        progress_line = objective_progress_text(energy_active, cooling_active, terminal_authorized)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glRotatef(pitch, 1, 0, 0)
        glRotatef(yaw, 0, 1, 0)
        glTranslatef(-cam_x, -cam_y, -cam_z)

        draw_floor_and_ceiling(
            current_map,
            level_config["floor_color"],
            level_config["ceiling_color"],
        )

        pulse_time = pygame.time.get_ticks()

        for row_index, row_string in enumerate(current_map):
            for col_index, cell in enumerate(row_string):
                block_x = col_index * BLOCK_SIZE
                block_z = row_index * BLOCK_SIZE

                if cell == "#":
                    draw_cube(block_x, 0, block_z, BLOCK_SIZE, WALL_HEIGHT, level_config["wall_color"])
                elif cell == "D":
                    color = level_config["door_open_color"] if door_open() else level_config["door_locked_color"]
                    if not door_open():
                        draw_cube(block_x, 0, block_z, BLOCK_SIZE, WALL_HEIGHT, color)
                        draw_beacon(block_x, 0.0, block_z, color, pulse_time, 3.5)
                    else:
                        draw_pickup(block_x, 0.4, block_z, BLOCK_SIZE * 0.18, color, pulse_time)
                elif cell == "E":
                    draw_panel(block_x, 0, block_z, BLOCK_SIZE * 0.55, level_config["energy_color"])
                    if not energy_active:
                        draw_beacon(block_x, 0.0, block_z, level_config["energy_color"], pulse_time)
                        draw_arrow_marker(block_x, 0.0, block_z, level_config["energy_color"], pulse_time)
                elif cell == "R":
                    draw_panel(block_x, 0, block_z, BLOCK_SIZE * 0.55, level_config["cooling_color"])
                    if energy_active and not cooling_active:
                        draw_beacon(block_x, 0.0, block_z, level_config["cooling_color"], pulse_time)
                        draw_arrow_marker(block_x, 0.0, block_z, level_config["cooling_color"], pulse_time)
                elif cell == "T":
                    draw_panel(block_x, 0, block_z, BLOCK_SIZE * 0.55, level_config["terminal_color"])
                    if energy_active and cooling_active and not terminal_authorized:
                        draw_beacon(block_x, 0.0, block_z, level_config["terminal_color"], pulse_time)
                        draw_arrow_marker(block_x, 0.0, block_z, level_config["terminal_color"], pulse_time)
                elif cell == "S":
                    draw_pickup(block_x, 0.7, block_z, BLOCK_SIZE * 0.34, level_config["exit_color"], pulse_time)
                    if door_open():
                        draw_beacon(block_x, 0.0, block_z, level_config["exit_color"], pulse_time)
                        draw_arrow_marker(block_x, 0.0, block_z, level_config["exit_color"], pulse_time)
                elif cell == "H":
                    draw_pickup(block_x, 0.5, block_z, BLOCK_SIZE * 0.20, level_config["hideout_color"], pulse_time)
                elif cell == "V":
                    draw_pickup(block_x, 0.6, block_z, BLOCK_SIZE * 0.22, level_config["steam_color"], pulse_time)
                elif cell == "M":
                    threat_color = level_config["threat_color"] if menace_triggered else (0.25, 0.05, 0.05)
                    draw_pickup(block_x, 0.5, block_z, BLOCK_SIZE * 0.22, threat_color, pulse_time)

        if creature_visible:
            draw_creature(creature_x, 0.0, creature_z, pulse_time)

        if result_state == "VITORIA" and pygame.time.get_ticks() - ending_started_at > 900:
            running = False

        draw_screen_overlay(screen_width, screen_height, overlay_alpha, overlay_color)

        glDisable(GL_DEPTH_TEST)
        screen = pygame.display.get_surface()
        systems_line = (
            f"Energia: {'OK' if energy_active else 'OFF'} | "
            f"Refrigeracao: {'OK' if cooling_active else 'OFF'} | "
            f"Terminal: {'OK' if terminal_authorized else 'OFF'} | "
            f"Saida: {'ABERTA' if door_open() else 'BLOQUEADA'}"
        )
        current_alert = alert_message if now <= alert_until else "Sem alerta imediato"
        creature_distance = (
            str(int(math.hypot(cam_x - creature_x, cam_z - creature_z)))
            if creature_visible
            else "--"
        )
        helper_line = interact_message or "Interacao: nenhuma | ESC para voltar ao mapa estelar"
        if now <= guidance_until and planet_name == "Arago":
            if not energy_active:
                helper_line = "Siga o brilho amarelo e pressione E no painel de energia"
            elif not cooling_active:
                helper_line = "Agora procure o painel azul da refrigeracao"
            elif not terminal_authorized:
                helper_line = "Vá ao terminal laranja e autorize a saida"
            elif not result_state == "VITORIA":
                helper_line = "Corra para o modulo verde de evacuacao"
        draw_hud_lines(
            screen,
            hud_font,
            [
                level_config["title"],
                current_objective,
                progress_line,
                systems_line,
                f"Criatura: {creature_state} | Distancia: {creature_distance}",
                f"Alerta: {current_alert}",
                f"Status: {status_message}",
                helper_line,
            ],
        )

        if show_intro:
            draw_center_message(
                screen,
                title_font,
                small_font,
                "ARAGO: ECO DE PRESSAO",
                [
                    "Objetivo: ativar Energia, Refrigeracao e Autorizacao para liberar a fuga.",
                    "Controles: WASD move, mouse olha, E interage, ESC volta ao mapa estelar.",
                    "Os paineis brilham por cor: amarelo, azul, laranja. A saida final brilha em verde.",
                    "O Escutador reage a ruido e presenca. SPACE, ENTER ou E para iniciar.",
                ],
            )
        glEnable(GL_DEPTH_TEST)

        pygame.display.flip()
        clock.tick(fps)

    return result_state


if __name__ == "__main__":
    pygame.init()
    start("Terra")
