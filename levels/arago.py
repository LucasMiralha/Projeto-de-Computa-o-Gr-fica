import math
import os
import random
import sys
from array import array
from collections import deque

import numpy as np

import pygame
from OpenGL.GL import *
from OpenGL.GLU import *
from pygame.locals import *

from core.graphics_utils import load_texture
from core.renderer import draw_cube, draw_floor_tile, draw_u_stairs, draw_computer, draw_alien_crystal, draw_exit_module, draw_creature, draw_textured_cube, draw_textured_floor_tile
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
        "wall": (0.10, 0.04, 0.03),
        "floor": (0.05, 0.03, 0.02),
        "ceiling": (0.03, 0.03, 0.04),
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


# --- Cache global para a máscara base da lanterna (calculada uma vez) ---
_flashlight_cache = {
    "base_light": None,     # Máscara de iluminação base (float32, shape sh×sw)
    "vignette": None,       # Máscara de vinheta (float32, shape sh×sw)
    "sw": 0,
    "sh": 0,
    "texture_id": None,     # Textura OpenGL reutilizável
}


def _build_flashlight_base(sw, sh):
    """Pré-calcula a máscara de iluminação radial e a vinheta.
    Executado apenas uma vez (ou quando a resolução muda)."""
    cx = sw / 2.0
    cy = sh * 0.52

    # Raios base da elipse da lanterna
    base_radius = min(sw, sh) * 0.32
    rx = base_radius * 1.25
    ry = base_radius * 1.0
    hotspot = 0.38

    # Coordenadas normalizadas de cada pixel
    xs = np.arange(sw, dtype=np.float32)
    ys = np.arange(sh, dtype=np.float32)
    px, py = np.meshgrid(xs, ys)  # shape (sh, sw)

    # Distância elíptica normalizada do centro
    dx = (px - cx) / max(1.0, rx)
    dy = (py - cy) / max(1.0, ry)
    dist = np.sqrt(dx * dx + dy * dy)

    # Calcula o mapa de luz em 3 zonas: hotspot, penumbra, escuridão
    light = np.zeros_like(dist)

    # Zona 1: Hotspot central brilhante
    mask_hot = dist < hotspot
    t_hot = dist[mask_hot] / hotspot
    light[mask_hot] = 1.0 - (t_hot * t_hot * 0.3)

    # Zona 2: Penumbra — falloff cúbico suave
    mask_pen = (dist >= hotspot) & (dist < 1.0)
    t_pen = (dist[mask_pen] - hotspot) / (1.0 - hotspot)
    light[mask_pen] = 0.7 * (1.0 - (t_pen * t_pen * t_pen))

    # Vinheta nos cantos
    corner_dx = (px - sw * 0.5) / (sw * 0.5)
    corner_dy = (py - sh * 0.5) / (sh * 0.5)
    vignette = np.clip((corner_dx * corner_dx + corner_dy * corner_dy) * 0.15, 0.0, 1.0)

    return light.astype(np.float32), vignette.astype(np.float32)


def draw_flashlight_overlay(width, height, pulse_time):
    """Renderiza um overlay de lanterna realista com gradiente suave,
    elipse, hotspot, penumbra, vinheta e flicker."""
    global _flashlight_cache

    # Resolução reduzida (1/4) — upscale suave via GL_LINEAR
    scale = 4
    sw = max(1, width // scale)
    sh = max(1, height // scale)

    # Reconstrói o cache se a resolução mudou
    if _flashlight_cache["sw"] != sw or _flashlight_cache["sh"] != sh:
        _flashlight_cache["base_light"], _flashlight_cache["vignette"] = _build_flashlight_base(sw, sh)
        _flashlight_cache["sw"] = sw
        _flashlight_cache["sh"] = sh
        # Libera a textura antiga se existir
        if _flashlight_cache["texture_id"] is not None:
            try:
                glDeleteTextures([_flashlight_cache["texture_id"]])
            except Exception:
                pass
        _flashlight_cache["texture_id"] = glGenTextures(1)

    base_light = _flashlight_cache["base_light"]  # (sh, sw)
    vignette = _flashlight_cache["vignette"]       # (sh, sw)
    texture_id = _flashlight_cache["texture_id"]

    # --- Modulação por frame: breath + flicker ---
    breath = 1.0 + math.sin(pulse_time * 0.0012) * 0.035
    flicker = 1.0 - random.uniform(0.0, 0.03)
    intensity = breath * flicker

    # Escala a luz pelo fator de intensidade (operação vetorial rápida)
    light = np.clip(base_light * intensity, 0.0, 1.0)

    # Escuridão base
    max_dark = 235.0

    # Alpha: quanto mais luz, mais transparente (menor alpha)
    alpha = (max_dark * (1.0 - light) + max_dark * vignette * 0.3)
    alpha = np.clip(alpha, 0, 255).astype(np.uint8)

    # Canal de cor quente no centro do feixe
    warmth = light * 0.5
    r = np.clip(12 + warmth * 30, 0, 255).astype(np.uint8)
    g = np.clip(8 + warmth * 18, 0, 255).astype(np.uint8)
    b = np.clip(5 + warmth * 5, 0, 255).astype(np.uint8)

    # Pixels escuros onde não há luz
    dark_mask = light <= 0.01
    r[dark_mask] = 0
    g[dark_mask] = 0
    b[dark_mask] = 0

    # Monta buffer RGBA (sh, sw, 4) — flip vertical para OpenGL (origem bottom-left)
    rgba = np.stack([r, g, b, alpha], axis=-1)
    rgba = np.ascontiguousarray(np.flipud(rgba))
    overlay_data = rgba.tobytes()

    # --- Upload e renderização via OpenGL ---
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
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, sw, sh, 0, GL_RGBA, GL_UNSIGNED_BYTE, overlay_data)
    glColor4f(1.0, 1.0, 1.0, 1.0)

    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 1.0); glVertex2f(0, 0)
    glTexCoord2f(1.0, 1.0); glVertex2f(width, 0)
    glTexCoord2f(1.0, 0.0); glVertex2f(width, height)
    glTexCoord2f(0.0, 0.0); glVertex2f(0, height)
    glEnd()

    glDisable(GL_TEXTURE_2D)
    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()


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


def load_sound(sound_path, volume=0.35):
    sound = pygame.mixer.Sound(sound_path)
    sound.set_volume(volume)
    return sound


def speed_up_sound(sound, speed_multiplier=1.35, volume=0.35, channels=2):
    if speed_multiplier <= 1.0:
        sound.set_volume(volume)
        return sound

    raw_samples = array("h")
    raw_samples.frombytes(sound.get_raw())
    if not raw_samples:
        sound.set_volume(volume)
        return sound

    total_frames = len(raw_samples) // channels
    accelerated_samples = array("h")
    frame_index = 0.0

    while int(frame_index) < total_frames:
        source_frame = int(frame_index) * channels
        for channel_index in range(channels):
            accelerated_samples.append(raw_samples[source_frame + channel_index])
        frame_index += speed_multiplier

    accelerated_sound = pygame.mixer.Sound(buffer=accelerated_samples.tobytes())
    accelerated_sound.set_volume(volume)
    return accelerated_sound


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
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sounds_path = os.path.join(project_root, "Assets", "Sounds")
    planet_textures_path = os.path.join(project_root, "Assets", "Planet Textures")
    custom_textures_path = os.path.join(project_root, "Assets", "Textures")
    environment_textures = {
        "wall": None,
        "floor": None,
        "ceiling": None,
    }

    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=22050, size=-16, channels=2)
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(3)
        collect_sound_path = os.path.join(sounds_path, "som_item.mp3")
        if os.path.exists(collect_sound_path):
            sounds["collect"] = load_sound(collect_sound_path, volume=0.34)
        else:
            sounds["collect"] = create_tone_sound([660, 880], 180, volume=0.28)
        sounds["wake"] = create_tone_sound([150, 180, 210], 420, volume=0.35)
        sounds["unlock"] = create_tone_sound([520, 660, 820], 320, volume=0.3)
        sounds["blocked"] = create_tone_sound([160, 120], 240, volume=0.3)
        sounds["victory"] = create_tone_sound([440, 554, 660], 520, volume=0.32)
        sounds["danger"] = create_tone_sound([260, 220], 260, volume=0.26)
        sounds["defeat"] = create_tone_sound([220, 165, 110], 700, volume=0.4)
        sounds["footstep"] = load_sound(os.path.join(sounds_path, "passos_arago.mp3"), volume=0.32)
        sounds["footstep_sprint"] = speed_up_sound(sounds["footstep"], speed_multiplier=1.45, volume=0.36)
        heart_sound_path = os.path.join(sounds_path, "coracao.mp3")
        if os.path.exists(heart_sound_path):
            sounds["heart"] = load_sound(heart_sound_path, volume=0.22)
            sounds["heart_mid"] = speed_up_sound(sounds["heart"], speed_multiplier=1.18, volume=0.28)
            sounds["heart_fast"] = speed_up_sound(sounds["heart"], speed_multiplier=1.35, volume=0.34)
        robot_sound_path = os.path.join(sounds_path, "robot_noise.mp3")
        if os.path.exists(robot_sound_path):
            sounds["robot_chase"] = load_sound(robot_sound_path, volume=0.26)

        wall_texture_path = os.path.join(custom_textures_path, "parede_arago.png")
        floor_texture_path = os.path.join(custom_textures_path, "chao_arago.png")
        ceiling_texture_path = os.path.join(custom_textures_path, "teto_arago.png")
        environment_textures["wall"] = load_texture(wall_texture_path, max_size=128)
        environment_textures["floor"] = load_texture(floor_texture_path, max_size=128)
        environment_textures["ceiling"] = load_texture(ceiling_texture_path, max_size=128)
    except pygame.error:
        sound_enabled = False

    clock = pygame.time.Clock()
    fps = 60

    # Restaura o mapa do save (essencial para mapas "random") ou gera um novo
    if saved_state and 'map_data' in saved_state:
        current_map = saved_state['map_data']
    else:
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

    # Restaura itens do save ou gera novos
    if saved_state and 'item_positions' in saved_state:
        item_positions = [tuple(pos) for pos in saved_state['item_positions']]
    else:
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
    footstep_channel = pygame.mixer.Channel(1) if sound_enabled else None
    item_channel = pygame.mixer.Channel(0) if sound_enabled else None
    heart_channel = pygame.mixer.Channel(2) if sound_enabled else None
    robot_channel = pygame.mixer.Channel(3) if sound_enabled else None
    current_footstep_name = None
    current_heart_name = None
    robot_chase_active = False
    pending_wake_sound_time = 0
    delta_seconds = 1.0 / fps
    previous_player_position = (cam_x, cam_z)

    def stop_level_audio():
        nonlocal current_footstep_name, current_heart_name, pending_wake_sound_time
        nonlocal robot_chase_active
        for channel in (item_channel, footstep_channel, heart_channel, robot_channel):
            if channel and channel.get_busy():
                channel.stop()
        current_footstep_name = None
        current_heart_name = None
        robot_chase_active = False
        pending_wake_sound_time = 0

    # Restauração completa do estado salvo
    if saved_state:
        cam_x = saved_state.get('cam_x', cam_x)
        cam_z = saved_state.get('cam_z', cam_z)
        yaw = saved_state.get('yaw', yaw)
        pitch = saved_state.get('pitch', pitch)
        stamina = saved_state.get('stamina', max_stamina)
        exhausted = saved_state.get('exhausted', False)
        items_collected = saved_state.get('items_collected', 0)
        # Restaura itens coletados como set de tuplas
        collected_list = saved_state.get('collected_items', [])
        collected_items = set(tuple(pos) for pos in collected_list)
        # Restaura criatura
        creature_x = saved_state.get('creature_x', creature_x)
        creature_z = saved_state.get('creature_z', creature_z)
        creature_visible = saved_state.get('creature_visible', creature_visible)
        previous_player_position = (cam_x, cam_z)

    # --- MENU DE PAUSA ---
    import os as _os
    _script_path = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _font_path = _os.path.join(_script_path, 'Assets', 'Fonts', 'united-sans-reg-bold.otf')
    
    try:
        fonte_botao = pygame.font.Font(_font_path, 28)
    except Exception:
        fonte_botao = pygame.font.SysFont('Arial', 28, bold=True)
    fonte_titulo = pygame.font.SysFont('Arial', 72, bold=True)

    _btn_color = (0, 0, 0, 0)
    _font_btn_color = (95, 198, 139, 255)
    _hover_btn_color = (95, 198, 139, 150)
    is_paused = False
    is_game_over = False
    is_victory = False

    # Moved

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
            'cam_z': cam_z,
            'yaw': yaw,
            'pitch': pitch,
            'stamina': stamina,
            'exhausted': exhausted,
            'items_collected': items_collected,
            'collected_items': [list(pos) for pos in collected_items],
            'item_positions': [list(pos) for pos in item_positions],
            'creature_x': creature_x,
            'creature_z': creature_z,
            'creature_visible': creature_visible,
            'map_data': current_map,
        }
        save_manager.save_level_save(planet.name, level_data)
        main = save_manager.load_main_save()
        save_manager.save_main_save(main.get('unlocked_planets', []), planet.name)
        cb_continuar()

    def cb_carregar_jogo():
        nonlocal running, result_state
        stop_level_audio()
        result_state = "LOAD_GAME"
        running = False

    def cb_voltar_menu():
        nonlocal running, result_state
        stop_level_audio()
        result_state = "MENU"
        running = False

    def cb_sair_desktop():
        stop_level_audio()
        pygame.quit()
        sys.exit()

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

    def cb_win_continue():
        nonlocal running, result_state
        stop_level_audio()
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
    
    def cb_restart_level():
        nonlocal running, result_state
        stop_level_audio()
        result_state = "RESTART"
        running = False
        
    title_game_over = Title(
        screen_width // 2 - 300, screen_height // 2 - 200, 600, 100,
        "VOCÊ MORREU", fonte_titulo, bg_color=(0, 0, 0, 0),
        text_color=(255, 50, 50, 255), align="center"
    )
    btn_restart_go = Button(
        screen_width // 2 - 150, screen_height // 2 - 100, 300, 50, "TENTAR DE NOVO",
        fonte_botao, cb_restart_level, base_color=_btn_color,
        hover_color=_hover_btn_color, text_color=_font_btn_color
    )

    # -- OTIMIZAÇÃO: COMPILAÇÃO DA DISPLAY LIST --
    mapa_display_list = glGenLists(1)
    glNewList(mapa_display_list, GL_COMPILE)
    for row_index, row_string in enumerate(current_map):
        for col_index, char in enumerate(row_string):
            block_x = col_index * BLOCK_SIZE
            block_z = row_index * BLOCK_SIZE

            # desenha o chão
            draw_textured_floor_tile(
                block_x,
                0,
                block_z,
                BLOCK_SIZE,
                texture_id=environment_textures["floor"],
                color=level_colors["floor"],
                uv_scale=1.0,
            )
            
            # desenha o teto
            draw_textured_floor_tile(
                block_x,
                WALL_HEIGHT,
                block_z,
                BLOCK_SIZE,
                texture_id=environment_textures["ceiling"],
                color=level_colors["ceiling"],
                uv_scale=1.0,
            )

            # desenha a parede
            if char == "#" or char == "P":
                draw_textured_cube(
                    block_x,
                    0,
                    block_z,
                    BLOCK_SIZE,
                    WALL_HEIGHT,
                    texture_id=environment_textures["wall"],
                    color=level_colors["wall"],
                    uv_scale=1.0,
                )
    glEndList()
    # --------------------------------------------

    running = True
    esc_held = False

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

        for event in pygame.event.get():
            if event.type == QUIT:
                stop_level_audio()
                pygame.quit()
                sys.exit()

            # Menu de pausa: captura eventos de UI
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
                if not is_paused and not is_game_over and not is_victory and event.key == K_e and planet.name == "Arago":
                    if near_item_position:
                        collected_items.add(near_item_position)
                        items_collected += 1
                        if sound_enabled and "collect" in sounds:
                            if item_channel:
                                item_channel.stop()
                                item_channel.play(sounds["collect"])
                            else:
                                play_sound(sound_enabled, sounds, "collect")
                        creature_profile = get_creature_profile(items_collected)
                        creature_state = creature_profile["state"]
                        creature_visible = True
                        creature_wake_time = pygame.time.get_ticks() + creature_profile["spawn_delay_ms"]
                        collect_sound_duration_ms = 0
                        if sound_enabled and "collect" in sounds:
                            collect_sound_duration_ms = int(sounds["collect"].get_length() * 1000)
                        pending_wake_sound_time = pygame.time.get_ticks() + max(220, collect_sound_duration_ms + 30)
                        remaining_count = TOTAL_ARAGO_ITEMS - items_collected
                        if remaining_count > 0:
                            status_message = f"Item coletado. Faltam {remaining_count} para liberar a saida."
                        else:
                            status_message = "Todos os 7 itens foram coletados. A saida foi liberada."
                            play_sound(sound_enabled, sounds, "unlock")
                    elif near_exit:
                        if exit_unlocked:
                            if not is_victory:
                                is_victory = True
                                pygame.mouse.set_visible(True)
                                pygame.event.set_grab(False)
                                status_message = "Evacuacao iniciada."
                                play_sound(sound_enabled, sounds, "victory")
                        else:
                            status_message = f"Saida bloqueada. Colete os 7 itens. Atual: {items_collected}/7."
                            play_sound(sound_enabled, sounds, "blocked")
                    else:
                        status_message = "Nenhum item ou saida ao alcance."

        # Atualiza hover dos botões de pausa
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

        if is_game_over or is_paused or is_victory:
            # Pula a lógica de jogo, vai direto pra renderização
            pass
        else:
            if pending_wake_sound_time and pygame.time.get_ticks() >= pending_wake_sound_time:
                play_sound(sound_enabled, sounds, "wake")
                pending_wake_sound_time = 0

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

            previous_cam_x = cam_x
            previous_cam_z = cam_z
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

            moved_distance = math.hypot(cam_x - previous_cam_x, cam_z - previous_cam_z)
            if moved_distance > 0.01 and sound_enabled and "footstep" in sounds and footstep_channel:
                desired_footstep_name = "footstep_sprint" if sprinting and "footstep_sprint" in sounds else "footstep"
                desired_sound = sounds[desired_footstep_name]
                if current_footstep_name != desired_footstep_name:
                    footstep_channel.stop()
                    current_footstep_name = desired_footstep_name
                if not footstep_channel.get_busy():
                    footstep_channel.play(desired_sound, loops=-1)
            elif footstep_channel and footstep_channel.get_busy():
                footstep_channel.stop()
                current_footstep_name = None

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

                if sound_enabled and heart_channel and "heart" in sounds:
                    heart_trigger_distance = BLOCK_SIZE * 8.0
                    if player_distance <= heart_trigger_distance:
                        heart_level = 0
                        if items_collected >= 5 or player_distance <= BLOCK_SIZE * 4.0:
                            heart_level = 2
                        elif items_collected >= 3 or player_distance <= BLOCK_SIZE * 6.0:
                            heart_level = 1

                        desired_heart_name = "heart"
                        if heart_level == 1 and "heart_mid" in sounds:
                            desired_heart_name = "heart_mid"
                        elif heart_level == 2 and "heart_fast" in sounds:
                            desired_heart_name = "heart_fast"

                        if current_heart_name != desired_heart_name:
                            heart_channel.stop()
                            current_heart_name = desired_heart_name
                        if not heart_channel.get_busy():
                            heart_channel.play(sounds[desired_heart_name], loops=-1)
                    elif heart_channel.get_busy():
                        heart_channel.stop()
                        current_heart_name = None

                if should_chase_player and now >= next_danger_sound_time:
                    play_sound(sound_enabled, sounds, "danger")
                    next_danger_sound_time = now + max(550, 1300 - (items_collected * 110))

                if sound_enabled and robot_channel and "robot_chase" in sounds:
                    if should_chase_player:
                        if not robot_chase_active:
                            robot_channel.stop()
                            robot_channel.play(sounds["robot_chase"], loops=-1)
                            robot_chase_active = True
                    elif robot_chase_active:
                        robot_channel.stop()
                        robot_chase_active = False

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
                    if not is_game_over:
                        status_message = "A criatura alcancou voce."
                        try:
                            pygame.mixer.Sound(_os.path.join(_script_path, 'Assets', 'Sounds', 'ai-01.mp3')).play()
                        except Exception as e:
                            print(f"Erro no som principal: {e}")
                            if sound_enabled and "defeat" in sounds:
                                sounds["defeat"].play() # Fallback pro som original do sistema se falhar
                        is_game_over = True
                        pygame.mouse.set_visible(True)
                        pygame.event.set_grab(False)
            elif items_collected > 0 and creature_spawn and creature_visible and now < creature_wake_time:
                status_message = "Voce ouviu algo se movendo pelos corredores."
                if heart_channel and heart_channel.get_busy():
                    heart_channel.stop()
                    current_heart_name = None
                if robot_channel and robot_channel.get_busy():
                    robot_channel.stop()
                    robot_chase_active = False
            elif heart_channel and heart_channel.get_busy():
                heart_channel.stop()
                current_heart_name = None
                if robot_channel and robot_channel.get_busy():
                    robot_channel.stop()
                    robot_chase_active = False

            previous_player_position = player_position

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glRotatef(pitch, 1, 0, 0)
        glRotatef(yaw, 0, 1, 0)
        glTranslatef(-cam_x, -cam_y, -cam_z)

        pulse_time = pygame.time.get_ticks()

        # Desenha a geometria estática utilizando Display List otimizada
        glCallList(mapa_display_list)

        if exit_position:
            draw_exit_module(
                exit_position[0],
                0,
                exit_position[1],
                BLOCK_SIZE * 0.82,
                level_colors["exit_locked"],
                level_colors["exit_unlocked"],
                exit_unlocked,
                pulse_time,
            )

        for item_x, item_z in item_positions:
            if (item_x, item_z) not in collected_items:
                draw_alien_crystal(
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

        draw_flashlight_overlay(screen_width, screen_height, pulse_time)
        draw_hud(screen_width, screen_height, hud_font, hud_lines)

        # --- RENDERIZAÇÃO DO MENU DE PAUSA / GAME OVER ---
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

            # Fundo avermelhado de sangue
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
            # Overlay 2D para o menu de pausa
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

            # Fundo escuro transparente
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
        delta_seconds = clock.tick(fps) / 1000.0

    stop_level_audio()
    return result_state


if __name__ == "__main__":
    pygame.init()
    start("Arago")
