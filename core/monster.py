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
    ):
        self.spawn_position = spawn_position
        self.block_size = block_size
        self.distance_fn = distance_fn
        self.pathfinder_fn = pathfinder_fn
        self.cutoff_target_fn = cutoff_target_fn
        self.cell_to_world_fn = cell_to_world_fn
        self.reset()

    def reset(self):
        if self.spawn_position:
            self.x, self.z = self.spawn_position
        else:
            self.x, self.z = (0.0, 0.0)
        self.yaw = 0.0
        self.path = []
        self.next_path_refresh = 0
        self.visible = False
        self.wake_time = 0
        self.target_position = self.spawn_position if self.spawn_position else (0.0, 0.0)
        self.last_state = self.get_state(0)
        self.next_danger_sound_time = 0

    @property
    def position(self):
        if hasattr(self, 'current_layer'):
            return (self.current_layer, self.x, self.z)
        return (self.x, self.z)

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
                "speed": 0.07,
                "awareness_radius": self.block_size * 4.0,
                "path_refresh_ms": 520,
                "spawn_delay_ms": 2500,
            }
        if items_collected <= 4:
            return {
                "state": state,
                "speed": 0.11,
                "awareness_radius": self.block_size * 7.0,
                "path_refresh_ms": 300,
                "spawn_delay_ms": 1000,
            }
        if items_collected <= 6:
            return {
                "state": state,
                "speed": 0.16,
                "awareness_radius": self.block_size * 12.0,
                "path_refresh_ms": 180,
                "spawn_delay_ms": 450,
            }
        return {
            "state": state,
            "speed": 0.22,
            "awareness_radius": self.block_size * 99.0,
            "path_refresh_ms": 90,
            "spawn_delay_ms": 120,
        }

    def reveal(self, items_collected, now):
        profile = self.get_profile(items_collected)
        self.visible = True
        self.wake_time = now + profile["spawn_delay_ms"]
        self.last_state = profile["state"]
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
    ):
        result = MonsterUpdateResult()
        profile = self.get_profile(items_collected)
        current_state = profile["state"]

        if current_state != self.last_state and items_collected > 0:
            result.state_changed = True
            self.last_state = current_state

        if items_collected <= 0 or not self.spawn_position or not self.visible or now < self.wake_time:
            return result

        result.player_distance = self.distance_fn(player_position, self.position)
        result.should_chase = (
            items_collected >= 5 or result.player_distance <= profile["awareness_radius"]
        )

        # Índices de X e Z no formato de posição: (x, z) vs (layer, x, z)
        _3d = hasattr(self, 'current_layer')
        _ix = 1 if _3d else 0  # índice do X
        _iz = 2 if _3d else 1  # índice do Z

        if result.should_chase:
            player_velocity_x = player_position[_ix] - previous_player_position[_ix]
            player_velocity_z = player_position[_iz] - previous_player_position[_iz]
            velocity_length = math.hypot(player_velocity_x, player_velocity_z)
            predictive_scale = min(self.block_size * 1.25, velocity_length * 10.0)
            if _3d:
                predicted_target = (
                    player_position[0],
                    player_position[_ix] + (player_velocity_x * predictive_scale),
                    player_position[_iz] + (player_velocity_z * predictive_scale),
                )
            else:
                predicted_target = (
                    player_position[_ix] + (player_velocity_x * predictive_scale),
                    player_position[_iz] + (player_velocity_z * predictive_scale),
                )
            if items_collected >= 4:
                self.target_position = self.cutoff_target_fn(
                    level_map,
                    player_position,
                    self.position,
                    predicted_target,
                )
            else:
                self.target_position = predicted_target
        else:
            if remaining_items:
                self.target_position = min(
                    remaining_items,
                    key=lambda item_pos: self.distance_fn(self.position, item_pos),
                )
            else:
                self.target_position = exit_position if exit_position else player_position

        if now >= self.next_path_refresh:
            self.path = self.pathfinder_fn(level_map, self.position, self.target_position)
            if not self.path and result.should_chase:
                self.path = self.pathfinder_fn(level_map, self.position, player_position)
                self.target_position = player_position
            self.next_path_refresh = now + profile["path_refresh_ms"]

        target_x = self.target_position[_ix]
        target_z = self.target_position[_iz]
        if len(self.path) > 1:
            path_entry = self.path[1]
            # Suporte a path 2D (row, col) e 3D (layer, row, col)
            next_row, next_col = path_entry[-2], path_entry[-1]
            target_x, target_z = self.cell_to_world_fn(next_row, next_col)

        delta_x = target_x - self.x
        delta_z = target_z - self.z
        distance = math.hypot(delta_x, delta_z)

        if distance > 0.01:
            step = min(profile["speed"], distance)
            self.x += (delta_x / distance) * step
            self.z += (delta_z / distance) * step
            self.yaw = math.degrees(math.atan2(delta_x, -delta_z))

        result.player_distance = self.distance_fn(player_position, self.position)
        result.caught_player = result.should_chase and result.player_distance <= 1.2
        return result
