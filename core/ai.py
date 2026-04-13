from core.physics_engine import *
from array import array
from collections import deque

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
        return "Cacando"
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


def world_to_cell(x, z):
    return int(round(z / BLOCK_SIZE)), int(round(x / BLOCK_SIZE))


def cell_to_world(row, col):
    return col * BLOCK_SIZE, row * BLOCK_SIZE


def is_walkable_cell(level_map, row, col):
    if row < 0 or row >= len(level_map) or col < 0 or col >= len(level_map[0]):
        return False
    return level_map[row][col] != "#"

def is_walkable_cell(level_map, row, col):
    if row < 0 or row >= len(level_map) or col < 0 or col >= len(level_map[0]):
        return False
    return level_map[row][col] != "#"

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