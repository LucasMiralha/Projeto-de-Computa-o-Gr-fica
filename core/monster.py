import math
from dataclasses import dataclass


@dataclass
class MonsterUpdateResult:
    state_changed: bool = False
    should_chase: bool = False
    caught_player: bool = False
    player_distance: float = 0.0


class MazeMonster:
    """Monstro reutilizavel para fases de labirinto com coleta e perseguicao."""

    def __init__(
        self,
        spawn_position,
        block_size,
        distance_fn,
        pathfinder_fn,
        cutoff_target_fn,
        cell_to_world_fn,
        spawn_layer=0,
        patrol_points=None,
        personality="blinky",
        display_name="Blinky",
        color=(0.9, 0.1, 0.1),
    ):
        self.spawn_position = spawn_position
        self.block_size = block_size
        self.distance_fn = distance_fn
        self.pathfinder_fn = pathfinder_fn
        self.cutoff_target_fn = cutoff_target_fn
        self.cell_to_world_fn = cell_to_world_fn
        self.spawn_layer = spawn_layer
        self.patrol_points = patrol_points or [spawn_position] if spawn_position else []
        self.personality = personality
        self.display_name = display_name
        self.color = color
        self.patrol_index = 0
        self.reset()

    def reset(self):
        if self.spawn_position:
            self.x, self.z = self.spawn_position
        else:
            self.x, self.z = (0.0, 0.0)
        self.current_layer = self.spawn_layer
        self.yaw = 0.0
        self.path = []
        self.next_path_refresh = 0
        self.visible = False
        self.wake_time = 0
        self.patrol_index = 0
        if self.patrol_points:
            patrol_x, patrol_z = self.patrol_points[self.patrol_index]
            self.target_position = (self.spawn_layer, patrol_x, patrol_z)
        elif self.spawn_position:
            self.target_position = (self.spawn_layer, self.spawn_position[0], self.spawn_position[1])
        else:
            self.target_position = (self.spawn_layer, 0.0, 0.0)
        self.last_state = self.get_state(0)
        self.next_danger_sound_time = 0
        self.body_radius = self.block_size * 0.16

    @property
    def position(self):
        return (self.x, self.z)

    @property
    def navigation_position(self):
        return (self.current_layer, self.x, self.z)

    def _get_cell(self, level_map, layer_index, row, col):
        if not (0 <= layer_index < len(level_map)):
            return None
        floor = level_map[layer_index]
        if not (0 <= row < len(floor)):
            return None
        if not (0 <= col < len(floor[row])):
            return None
        return floor[row][col]

    def _is_wall_at_position(self, level_map, x, z, layer_index):
        radius = self.body_radius
        for sample_x in (x - radius, x, x + radius):
            for sample_z in (z - radius, z, z + radius):
                row = int(round(sample_z / self.block_size))
                col = int(round(sample_x / self.block_size))
                char = self._get_cell(level_map, layer_index, row, col)
                if char is None or char in ['P', 'V', ' ', 'M']:
                    return True
        return False

    def get_state(self, items_collected):
        if items_collected <= 0:
            return "Adormecida"
        if items_collected <= 2:
            return "Atenta"
        if items_collected <= 4:
            return "Cacando"
        if items_collected <= 6:
            return "Agressiva"
        return "Furiosa"

    def get_profile(self, items_collected):
        state = self.get_state(items_collected)
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
                "speed": 0.15,
                "awareness_radius": self.block_size * 4.0,
                "path_refresh_ms": 520,
                "spawn_delay_ms": 2500,
            }
        if items_collected <= 4:
            return {
                "state": state,
                "speed": 0.21,
                "awareness_radius": self.block_size * 7.0,
                "path_refresh_ms": 300,
                "spawn_delay_ms": 1000,
            }
        if items_collected <= 6:
            return {
                "state": state,
                "speed": 0.28,
                "awareness_radius": self.block_size * 12.0,
                "path_refresh_ms": 180,
                "spawn_delay_ms": 450,
            }
        return {
            "state": state,
            "speed": 0.36,
            "awareness_radius": self.block_size * 99.0,
            "path_refresh_ms": 90,
            "spawn_delay_ms": 120,
        }

    def reveal(self, items_collected, now):
        profile = self.get_profile(items_collected)
        self.visible = True
        self.wake_time = now + profile["spawn_delay_ms"]
        self.last_state = profile["state"]
        if self.patrol_points:
            patrol_x, patrol_z = self.patrol_points[self.patrol_index]
            self.target_position = (self.spawn_layer, patrol_x, patrol_z)
        else:
            self.target_position = (self.spawn_layer, self.spawn_position[0], self.spawn_position[1])
        return profile

    def is_awake(self, now):
        return self.visible and now >= self.wake_time

    def get_hud_status(self, items_collected, now):
        state = self.get_state(items_collected)
        if not self.visible:
            return f"Criatura: {state}", (200, 180, 180)
        if now < self.wake_time:
            return f"Criatura: {state} (despertando)", (255, 185, 120)
        return f"Criatura: {state}", (255, 140, 140)

    def update(
        self,
        level_map,
        player_position,
        previous_player_position,
        items_collected,
        remaining_items,
        exit_position,
        now,
        anchor_position=None,
    ):
        result = MonsterUpdateResult()
        profile = self.get_profile(items_collected)
        current_state = profile["state"]

        if current_state != self.last_state and items_collected > 0:
            result.state_changed = True
            self.last_state = current_state

        if items_collected <= 0 or not self.spawn_position or not self.visible or now < self.wake_time:
            self.current_mode = "ADORMECIDO"
            return result

        result.player_distance = self.distance_fn(player_position, self.navigation_position)
        result.should_chase = (
            items_collected >= 5 or result.player_distance <= profile["awareness_radius"]
        )

        if result.should_chase:
            player_velocity_x = player_position[1] - previous_player_position[1]
            player_velocity_z = player_position[2] - previous_player_position[2]
            velocity_length = math.hypot(player_velocity_x, player_velocity_z)
            predictive_scale = min(self.block_size * 1.25, velocity_length * 10.0)
            predicted_target = (
                player_position[0],
                player_position[1] + (player_velocity_x * predictive_scale),
                player_position[2] + (player_velocity_z * predictive_scale),
            )

            if self.personality == "blinky":
                self.target_position = player_position
            elif self.personality == "pinky":
                self.target_position = predicted_target
            elif self.personality == "inky":
                if anchor_position is None:
                    self.target_position = predicted_target
                else:
                    offset_x = predicted_target[1] - anchor_position[1]
                    offset_z = predicted_target[2] - anchor_position[2]
                    self.target_position = (
                        predicted_target[0],
                        predicted_target[1] + offset_x,
                        predicted_target[2] + offset_z,
                    )
            elif self.personality == "clyde":
                if result.player_distance > self.block_size * 3.5:
                    self.target_position = player_position
                else:
                    patrol_x, patrol_z = self.patrol_points[0] if self.patrol_points else self.spawn_position
                    self.target_position = (self.spawn_layer, patrol_x, patrol_z)
            elif items_collected >= 4:
                self.target_position = self.cutoff_target_fn(
                    level_map,
                    player_position,
                    self.navigation_position,
                    predicted_target,
                    self.current_layer,
                )
            else:
                self.target_position = predicted_target
        else:
            if not self.patrol_points:
                self.patrol_points = [self.spawn_position]
            patrol_target = (self.current_layer, self.target_position[1], self.target_position[2]) if len(self.target_position) == 3 else (self.current_layer, self.target_position[0], self.target_position[1])
            if self.distance_fn(self.navigation_position, patrol_target) <= self.block_size * 0.5:
                self.patrol_index = (self.patrol_index + 1) % len(self.patrol_points)
                patrol_x, patrol_z = self.patrol_points[self.patrol_index]
                self.target_position = (self.spawn_layer, patrol_x, patrol_z)

        if now >= self.next_path_refresh:
            self.path = self.pathfinder_fn(level_map, self.navigation_position, self.target_position)
            if not self.path and result.should_chase:
                self.path = self.pathfinder_fn(level_map, self.navigation_position, player_position)
                self.target_position = player_position
            self.next_path_refresh = now + profile["path_refresh_ms"]

        target_layer, target_x, target_z = self.target_position
        if len(self.path) > 1:
            next_layer, next_row, next_col = self.path[1]
            if next_layer != self.current_layer:
                self.current_layer = next_layer
                self.path.pop(0)
                if len(self.path) > 1:
                    next_layer, next_row, next_col = self.path[1]
            target_x, target_z = self.cell_to_world_fn(next_row, next_col)
            target_layer = next_layer

        delta_x = target_x - self.x
        delta_z = target_z - self.z
        distance = math.hypot(delta_x, delta_z)

        if distance > 0.01:
            step = min(profile["speed"], distance)
            next_x = self.x + (delta_x / distance) * step
            next_z = self.z + (delta_z / distance) * step

            if not self._is_wall_at_position(level_map, next_x, self.z, self.current_layer):
                self.x = next_x
            if not self._is_wall_at_position(level_map, self.x, next_z, self.current_layer):
                self.z = next_z
            self.yaw = math.degrees(math.atan2(delta_x, -delta_z))

        self.current_layer = target_layer if distance <= 0.05 else self.current_layer
        result.player_distance = self.distance_fn(player_position, self.navigation_position)
        result.caught_player = result.should_chase and result.player_distance <= 1.2
        self.current_mode = "PROCURA" if result.should_chase else "PATRULHA"
        return result
