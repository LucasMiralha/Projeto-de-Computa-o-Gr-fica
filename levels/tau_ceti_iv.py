import os
import pygame
import sys
import math
import random
import heapq
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *


from core.renderer import draw_cube, draw_floor_tile, draw_u_stairs, draw_computer
from core.physics_engine import (BLOCK_SIZE, WALL_HEIGHT, is_wall, 
                                 has_ramp_below, get_target_y)
from core.ui import Button, Title
import core.save_manager as save_manager

# configura o OpenGL para desenhar em pixels (2D)
def prepare_2d(width, height):
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_DEPTH_TEST)

# restaura o OpenGL para o modo perspectiva (3D)
def prepare_3d():
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()

# --- SISTEMA DE PATHFINDING E WAYPOINTS ---

def _is_trap_tile(y, z, x, map3d):
    """
    Verifica se um tile é uma 'armadilha de queda': um tile andável que tem
    uma escada no andar de baixo. Pisar nesse tile faz get_target_y puxar
    a entidade para a escada abaixo, impedindo trânsito horizontal seguro.
    """
    if y <= 0:
        return False
    if 0 <= z < len(map3d[y-1]) and 0 <= x < len(map3d[y-1][z]):
        if map3d[y-1][z][x] in ['<', '>', '^', 'v']:
            return True
    return False

def get_walkable_neighbors(y, z, x, map3d):
    neighbors = []
    max_y = len(map3d)
    stair_chars = ['<', '>', '^', 'v']
    
    # Movimentos possíveis no mesmo andar
    directions = [(0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1)]
    walkable_chars = ['.', '<', '>', '^', 'v', '@', 'A', 'M']
    
    for dy, dz, dx in directions:
        ny, nz, nx = y + dy, z + dz, x + dx
        
        # Verificação em cascata segura para matrizes irregulares
        if 0 <= ny < max_y:
            if 0 <= nz < len(map3d[ny]):
                if 0 <= nx < len(map3d[ny][nz]):
                    if map3d[ny][nz][nx] in walkable_chars:
                        # Bloqueia tiles armadilha (escada no andar de baixo)
                        # para evitar que o A* crie rotas que passem por cima
                        # de escadas — get_target_y puxaria o alien para baixo
                        if not _is_trap_tile(ny, nz, nx, map3d):
                            neighbors.append((ny, nz, nx))
                        
    # Movimento Vertical (Subir/Descer Escadas)
    # Proteção extra: garantir que estamos dentro dos limites antes de ler char_current
    if 0 <= y < max_y and 0 <= z < len(map3d[y]) and 0 <= x < len(map3d[y][z]):
        char_current = map3d[y][z][x]
        
        # Se estiver em uma escada, pode subir para o andar de cima
        if char_current in stair_chars and y + 1 < max_y:
            # NÃO adiciona o bloco diretamente acima (y+1, z, x) — ele
            # é sempre um tile armadilha (tem esta escada no andar de baixo).
            # Em vez disso, só adiciona os vizinhos HORIZONTAIS seguros no andar de cima.
            for dz2, dx2 in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nz2, nx2 = z + dz2, x + dx2
                if 0 <= nz2 < len(map3d[y+1]) and 0 <= nx2 < len(map3d[y+1][nz2]):
                    if map3d[y+1][nz2][nx2] in walkable_chars:
                        # Só adiciona se o tile de destino NÃO for armadilha
                        if not _is_trap_tile(y+1, nz2, nx2, map3d):
                            neighbors.append((y+1, nz2, nx2))
                    
        # Se o bloco de baixo for uma escada, pode descer
        if y - 1 >= 0:
            # Verifica se o andar de baixo é grande o suficiente
            if 0 <= z < len(map3d[y-1]) and 0 <= x < len(map3d[y-1][z]):
                if map3d[y-1][z][x] in stair_chars:
                    neighbors.append((y-1, z, x))
            
            # Também verifica os 4 vizinhos horizontais no andar de baixo
            # (pode descer para um tile adjacente que tenha escada)
            for dz2, dx2 in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nz2, nx2 = z + dz2, x + dx2
                if 0 <= nz2 < len(map3d[y-1]) and 0 <= nx2 < len(map3d[y-1][nz2]):
                    if map3d[y-1][nz2][nx2] in stair_chars:
                        neighbors.append((y-1, nz2, nx2))

    return neighbors

def get_stair_traversal_points(block_x, base_y, block_z, direction_char, going_up):
    """
    Gera 4 sub-waypoints para o alien atravessar fisicamente uma escada em U.
    O alien precisa caminhar pelos dois lances da escada para que a física
    (get_target_y) ajuste sua altura Y progressivamente.
    
    A ordem dos pontos traça o percurso em U:
      Lance 1 (bottom) → Landing → Lance 2 (top)
    Para descer, a ordem é invertida.
    """
    q = BLOCK_SIZE * 0.45  # Offset XZ dentro do bloco (1.8 para BLOCK_SIZE=4.0)
    
    # Y do andar de destino (usado pelo is_climbing para evitar recálculo durante a subida)
    if going_up:
        dest_wy = (int(base_y / WALL_HEIGHT) + 1) * WALL_HEIGHT + 2.0
    else:
        dest_wy = int(base_y / WALL_HEIGHT) * WALL_HEIGHT + 2.0
    
    # Sub-waypoints na ordem de SUBIDA, derivados da rotação em get_stair_height:
    # '^' (sem rotação):  Lane 1 = SE, Landing = N, Lane 2 = SW
    # 'v' (180°):         Lane 1 = NW, Landing = S, Lane 2 = NE
    # '<' (90° CCW):      Lane 1 = NE, Landing = W, Lane 2 = SE
    # '>' (90° CW):       Lane 1 = SW, Landing = E, Lane 2 = NW
    stair_paths = {
        '^': [(+q, +q), (+q, -q), (-q, -q), (-q, +q)],
        'v': [(-q, -q), (-q, +q), (+q, +q), (+q, -q)],
        '<': [(+q, -q), (-q, -q), (-q, +q), (+q, +q)],
        '>': [(-q, +q), (+q, +q), (+q, -q), (-q, -q)],
    }
    
    offsets = stair_paths.get(direction_char, [(0, 0)])
    points = [(block_x + dx, dest_wy, block_z + dz) for dx, dz in offsets]
    
    return points if going_up else points[::-1]

def generate_precise_waypoints(grid_path, map3d):
    waypoints = []
    if not grid_path: return waypoints
    
    for i in range(len(grid_path)):
        y, z, x = grid_path[i]
        wx = x * BLOCK_SIZE
        wy = (y * WALL_HEIGHT) + 2.0 
        wz = z * BLOCK_SIZE
        
        # Verifica se o tile atual é uma escada
        char = None
        if 0 <= y < len(map3d) and 0 <= z < len(map3d[y]) and 0 <= x < len(map3d[y][z]):
            char = map3d[y][z][x]
        
        if char in ['<', '>', '^', 'v']:
            # Determina se há transição de andar neste ponto do caminho
            going_up = None
            
            # Próximo nó está em andar acima → subindo
            if i < len(grid_path) - 1 and grid_path[i+1][0] > y:
                going_up = True
            # Nó anterior estava em andar acima → descendo
            elif i > 0 and grid_path[i-1][0] > y:
                going_up = False
            
            if going_up is not None:
                # Gera sub-waypoints que traçam o percurso da escada em U
                traversal = get_stair_traversal_points(wx, y * WALL_HEIGHT, wz, char, going_up)
                waypoints.extend(traversal)
                continue  # Pula o waypoint normal do tile de escada
        
        waypoints.append((wx, wy, wz))
    return waypoints

def a_star_3d(start_node, target_node, map3d):
    # start_node e target_node são tuplas (y, z, x)
    open_set = []
    heapq.heappush(open_set, (0, start_node))
    came_from = {}
    
    g_score = {start_node: 0}
    
    def heuristic(a, b):
        return abs(a[0]-b[0]) + abs(a[1]-b[1]) + abs(a[2]-b[2])

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == target_node:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]

            return path[::-1]

        for neighbor in get_walkable_neighbors(current[0], current[1], current[2], map3d):
            # Custo extra para subir/descer andares para preferir caminhos planos se possível
            cost_move = 1 if neighbor[0] == current[0] else 2.5
            tentative_g_score = g_score[current] + cost_move
            
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score = tentative_g_score + heuristic(neighbor, target_node)
                heapq.heappush(open_set, (f_score, neighbor))
                
    return [] # Sem caminho

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

def draw_puzzle_glyph(character, x_offset):
    glPushMatrix()
    # Move a "caneta" para o lado esquerdo ou direito do '='
    glTranslatef(x_offset, 0, 0)
    
    glColor3f(0.8, 0.2, 0.2) # Mantém a cor vermelha da pichação
    glBegin(GL_LINES)

    # Proporções da letra (meia altura e meia largura)
    h = 0.2  
    w = 0.15 

    if character == 'N':
        glVertex3f(-w, -h, 0); glVertex3f(-w, h, 0)   # Perna esquerda
        glVertex3f(-w, h, 0);  glVertex3f(w, -h, 0)   # Diagonal
        glVertex3f(w, -h, 0);  glVertex3f(w, h, 0)    # Perna direita
        
    elif character == 'S':
        glVertex3f(w, h, 0);   glVertex3f(-w, h, 0)   # Topo
        glVertex3f(-w, h, 0);  glVertex3f(-w, 0, 0)   # Esquerda cima
        glVertex3f(-w, 0, 0);  glVertex3f(w, 0, 0)    # Meio
        glVertex3f(w, 0, 0);   glVertex3f(w, -h, 0)   # Direita baixo
        glVertex3f(w, -h, 0);  glVertex3f(-w, -h, 0)  # Base
        
    elif character == 'L':
        glVertex3f(-w, h, 0);  glVertex3f(-w, -h, 0)  # Perna vertical
        glVertex3f(-w, -h, 0); glVertex3f(w, -h, 0)   # Base horizontal
        
    elif character == 'O':
        glVertex3f(-w, h, 0);  glVertex3f(w, h, 0)    # Topo
        glVertex3f(w, h, 0);   glVertex3f(w, -h, 0)   # Direita
        glVertex3f(w, -h, 0);  glVertex3f(-w, -h, 0)  # Base
        glVertex3f(-w, -h, 0); glVertex3f(-w, h, 0)   # Esquerda
        
    elif character == 'T':
        glVertex3f(-w, h, 0);  glVertex3f(w, h, 0)    # Barra superior
        glVertex3f(0, h, 0);   glVertex3f(0, -h, 0)   # Haste central
        
    elif character == 'C':
        glVertex3f(w, h, 0);   glVertex3f(-w, h, 0)   # Topo
        glVertex3f(-w, h, 0);  glVertex3f(-w, -h, 0)  # Esquerda
        glVertex3f(-w, -h, 0); glVertex3f(w, -h, 0)   # Base
        
    elif character == 'I':
        glVertex3f(-w, h, 0);  glVertex3f(w, h, 0)    # Topo
        glVertex3f(0, h, 0);   glVertex3f(0, -h, 0)   # Haste central
        glVertex3f(-w, -h, 0); glVertex3f(w, -h, 0)   # Base
        
    elif character == 'V':
        glVertex3f(-w, h, 0);  glVertex3f(0, -h, 0)   # Diagonal esquerda desce
        glVertex3f(0, -h, 0);  glVertex3f(w, h, 0)    # Diagonal direita sobe

    glEnd()
    glPopMatrix()

def draw_equals_sign():
    glBegin(GL_LINES)
    glColor3f(0.8, 0.2, 0.2) # Vermelho pichação
    glVertex3f(-0.15, 0.1, 0); glVertex3f(0.15, 0.1, 0)
    glVertex3f(-0.15, -0.1, 0); glVertex3f(0.15, -0.1, 0)
    glEnd()

def draw_graffiti_cube(x, y, z, char_fixo, char_sorteado):
    # Desenha o cubo base (parede)
    draw_cube(x, y, z, BLOCK_SIZE, WALL_HEIGHT, color=(0.15, 0.2, 0.15))
    
    offset = (BLOCK_SIZE / 2) + 0.02 # Pequeno recuo para evitar z-fighting
    glLineWidth(3.0)
    
    for i in range(4): # Desenha nas 4 faces verticais
        glPushMatrix()
        glTranslatef(x, y + (WALL_HEIGHT / 2), z)
        glRotatef(i * 90, 0, 1, 0)
        glTranslatef(0, 0, offset)
        
        # Desenha "LetraFixa = LetraSorteada"
        # Exemplo: N = T
        draw_puzzle_glyph(char_fixo, -0.6) # Lado esquerdo do '='
        draw_equals_sign()                # O símbolo '='
        draw_puzzle_glyph(char_sorteado, 0.6) # Lado direito do '='
        
        glPopMatrix()

def load_alien_texture(image_path):
    try:
        image = pygame.image.load(image_path).convert_alpha()
        img_data = pygame.image.tostring(image, "RGBA", True)
        width, height = image.get_size()
        
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
        return tex_id
    except Exception as e:
        print(f"Aviso: Textura do alien não encontrada em {image_path}")
        return None

def draw_billboard_alien(x, y, z, tex_id, size, is_flipped, player_yaw):
    glPushMatrix()
    glTranslatef(x, y, z)
    # Gira o alien para sempre encarar a câmera do jogador!
    glRotatef(player_yaw, 0, 1, 0)
    
    if tex_id: 
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        
        # Ativa o teste alpha para o fundo da imagem PNG ficar transparente
        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GREATER, 0.1)
    

    glBegin(GL_QUADS)
    glColor3f(1.0, 1.0, 1.0)
    
    # Faz o flip horizontal manipulando as coordenadas UV da imagem
    u_left = 1.0 if is_flipped else 0.0
    u_right = 0.0 if is_flipped else 1.0
    
    half = size / 2.0
    glTexCoord2f(u_left, 0.0); glVertex3f(-half, 0, 0)
    glTexCoord2f(u_right, 0.0); glVertex3f(half, 0, 0)
    glTexCoord2f(u_right, 1.0); glVertex3f(half, size, 0)
    glTexCoord2f(u_left, 1.0); glVertex3f(-half, size, 0)
    glEnd()

    if tex_id: 
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_ALPHA_TEST)
    
    glPopMatrix()

# --- CLASSE DO ALIEN (FSM) ---

class AlienFSM:
    def __init__(self, start_x, start_y, start_z, map3d):
        self.x = start_x
        self.y = start_y
        self.z = start_z
        self.map3d = map3d
        
        self.state = "WANDERING"
        self.path_waypoints = []
        
        # Guarda o alvo atual para o texto de debug
        self.target_wx = 0.0
        self.target_wy = 0.0
        self.target_wz = 0.0
        
        self.speed = 0.20 
        self.chasing_speed = 0.18
        self.target_grid = None
        self.recalc_timer = 0
        self.valid_floors = len(map3d) - 1
        
        # Animação de flip do sprite (simula caminhada)
        self.is_flipped = False
        self.flip_timer = 0
        self.flip_interval = 20  # Troca a cada 20 frames (~0.33s a 60fps)

    def grid_coords(self, wx, wy, wz):
        """ Converte world coordinates para índices da matriz """
        # Usa round() para consistência com physics_engine (is_wall, get_target_y)
        gx = max(0, int(round(wx / BLOCK_SIZE)))
        pe_y = wy - 2.0
        gy = max(0, int(math.floor((pe_y + 0.5) / WALL_HEIGHT)))
        gz = max(0, int(round(wz / BLOCK_SIZE)))
        return (gy, gz, gx)

    def get_random_walkable_node(self):
        # Tenta achar um ponto aleatório andável
        for _ in range(50):
            gy = random.randint(0, self.valid_floors - 1)
            
            # Pega o limite de Z para este andar específico (gy)
            max_z = len(self.map3d[gy])
            if max_z == 0: continue
            gz = random.randint(0, max_z - 1)
            
            # Pega o limite de X para esta linha específica (gz)
            max_x = len(self.map3d[gy][gz])
            if max_x == 0: continue
            gx = random.randint(0, max_x - 1)
            
            if self.map3d[gy][gz][gx] == '.':
                return (gy, gz, gx)
                
        return self.grid_coords(self.x, self.y, self.z) # fallback

    def set_target_and_path(self, target_wx, target_wy, target_wz):
        # Salva o alvo físico atual
        self.target_wx = target_wx
        self.target_wy = target_wy
        self.target_wz = target_wz
        
        start_node = self.grid_coords(self.x, self.y, self.z)
        target_node = self.grid_coords(target_wx, target_wy, target_wz)
        
        grid_path = a_star_3d(start_node, target_node, self.map3d)
        self.path_waypoints = generate_precise_waypoints(grid_path, self.map3d)

    def trigger_hunt(self, comp_wx, comp_wy, comp_wz):
        self.state = "HUNTING"
        self.set_target_and_path(comp_wx, comp_wy, comp_wz)

    def update(self, player_x, player_y, player_z, collision_map):
        current_speed = self.chasing_speed if self.state == "CHASING" else self.speed
        dist_to_player = math.hypot(math.hypot(self.x - player_x, self.z - player_z), (self.y + 2.0) - player_y)

        # Lógica de Transição de Estados
        if self.state == "WANDERING":
            if not self.path_waypoints:
                r_node = self.get_random_walkable_node()
                current_node = self.grid_coords(self.x, self.y, self.z)
                if r_node != current_node:
                    rx = r_node[2] * BLOCK_SIZE   
                    ry = (r_node[0] * WALL_HEIGHT) + 2.0 
                    rz = r_node[1] * BLOCK_SIZE   
                    self.set_target_and_path(rx, ry, rz)
                
            if dist_to_player < 20.0:
                self.state = "CHASING"

        elif self.state == "HUNTING":
            if dist_to_player < 20.0: 
                self.state = "CHASING"
            elif not self.path_waypoints: 
                self.state = "WANDERING"

        elif self.state == "CHASING":
            # Verifica se ele está executando uma subida/descida de escada (Diferença de Y > 1.0)
            is_climbing = False
            if self.path_waypoints:
                target_py = self.path_waypoints[0][1]
                if abs(target_py - self.y) > 1.0:
                    is_climbing = True
            
            # SÓ recalcula a rota para o jogador se ele estiver em terreno plano!
            if not is_climbing:
                self.recalc_timer -= 1
                if self.recalc_timer <= 0:
                    # Só recalcula se o jogador se moveu significativamente
                    player_moved = math.hypot(player_x - self.target_wx, player_z - self.target_wz) > 4.0
                    if player_moved or not self.path_waypoints:
                        self.set_target_and_path(player_x, player_y, player_z)
                    self.recalc_timer = 90
                
            if dist_to_player > 35.0:
                self.state = "WANDERING"
                self.path_waypoints = [] 
        
        # --- MOVIMENTO FÍSICO (GUIADO POR WAYPOINTS) ---
        if self.path_waypoints:
            target_px, target_py, target_pz = self.path_waypoints[0]
            
            dx = target_px - self.x
            dz = target_pz - self.z
            
            dist_to_wp_xz = math.hypot(dx, dz)
            
            # Usa distância XZ para completar waypoints — a altura Y
            # é controlada pela física (get_target_y), não pelo pathfinding
            if dist_to_wp_xz <= 1.0: 
                self.path_waypoints.pop(0)
            else:
                if dist_to_wp_xz > 0.05:
                    self.x += (dx / dist_to_wp_xz) * current_speed
                    self.z += (dz / dist_to_wp_xz) * current_speed
                
                # Alterna o flip do sprite enquanto se move (animação de caminhada)
                self.flip_timer += 1
                if self.flip_timer >= self.flip_interval:
                    self.is_flipped = not self.is_flipped
                    self.flip_timer = 0

        # --- FÍSICA DAS ESCADAS E GRAVIDADE ---
        # Usa atribuição direta (como o jogador faz com player_y) em vez de lerp.
        # O lerp antigo (0.2) era muito lento para escadas — o alien nunca
        # ganhava altura suficiente antes de sair do bloco da escada.
        target_floor_y = get_target_y(self.x, self.y, self.z, self.map3d)
        self.y = target_floor_y

# loop principal
def start(planet, saved_state=None):
    # Restaura o puzzle_mapping do save (para manter coerência) ou gera um novo
    if saved_state and 'puzzle_mapping' in saved_state:
        puzzle_mapping = saved_state['puzzle_mapping']
    else:
        letras_puzzle = ['T', 'C', 'I', 'V']
        random.shuffle(letras_puzzle)
        puzzle_mapping = {
            'N': letras_puzzle[0],
            'S': letras_puzzle[1],
            'L': letras_puzzle[2],
            'O': letras_puzzle[3]
        }

    screen_info = pygame.display.Info()
    screen_width = screen_info.current_w
    screen_height = screen_info.current_h
    
    # garante que o contexto OpenGL está limpo e focado
    pygame.display.set_mode((screen_width, screen_height), DOUBLEBUF | OPENGL | FULLSCREEN)
    
    init_opengl_fps(screen_width, screen_height)
    
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)
    
    # Fontes para HUD e UI do Computador
    hud_font = pygame.font.SysFont("consolas", 24, bold=True)
    comp_font_large = pygame.font.SysFont("consolas", 48, bold=True)

    clock = pygame.time.Clock()
    FPS = 60

    current_map = planet.layout

    import copy
    collision_map = copy.deepcopy(current_map)
    for y_index, andar in enumerate(collision_map):
        for z_index, linha in enumerate(andar):
            linha_list = list(linha)
            for x_index, char in enumerate(linha_list):
                if char in ['N', 'S', 'L', 'O']:
                    linha_list[x_index] = 'P'
                elif char == 'A':
                    # Importante: Tratamos o spawn do alien como ponto andável '.'
                    linha_list[x_index] = '.' 
                elif char == '@':
                    linha_list[x_index] = '.'
            collision_map[y_index][z_index] = "".join(linha_list)
    
    computers_data = []
    cam_x, cam_y, cam_z = 0.0, 2.0, 0.0
    yaw, pitch = 0.0, 0.0

    # encontra o '@' (spawn) varrendo a matriz 3D
    spawn_x, spawn_y, spawn_z = 0, 0, 0
    alien_spawn_x, alien_spawn_y, alien_spawn_z = 0, 0, 0
    for y_index, andar in enumerate(current_map):
        for z_index, linha in enumerate(andar):
            for x_index, char in enumerate(linha):
                # Calculando as posições reais no mundo 3D
                world_x = x_index * 4.0 # BLOCK_SIZE
                world_y = y_index * 4.0 # WALL_HEIGHT
                world_z = z_index * 4.0 # BLOCK_SIZE

                if char == '@':
                    spawn_x = x_index * BLOCK_SIZE
                    spawn_y = (y_index * WALL_HEIGHT) + 2.0 # altura da câmera baseada no andar
                    spawn_z = z_index * BLOCK_SIZE

                elif char == 'A':
                    alien_spawn_x = world_x
                    alien_spawn_y = world_y + 2.0 
                    alien_spawn_z = world_z
                
                elif char == 'M':
                    # Gera o enigma para este computador específico
                    tamanho_seq = random.randint(4, 9)
                    seq_gerada = "".join(random.choices(['N', 'S', 'O', 'L'], k=tamanho_seq))
                    # Traduz a sequência para a resposta esperada
                    resposta_esperada = "".join([puzzle_mapping[letra] for letra in seq_gerada])
                    
                    computers_data.append({
                        'x': world_x, 
                        'y': world_y, 
                        'z': world_z,
                        'sequence': seq_gerada,
                        'expected': resposta_esperada,
                        'current_input': "",
                        'resolved': False
                    })
    
    alien_ai = AlienFSM(alien_spawn_x, alien_spawn_y, alien_spawn_z, collision_map)

    # --- VARIÁVEIS DE ESTADO DA UI ---
    interacting_comp = None # Computador atualmente aberto
    error_blink_timer = 0   # Timer para piscar a tela de vermelho
                    
    # Verificação de posição inicial: Se tiver save state, aplica as coordenadas dele. Senão, vai no spawn padrao
    if saved_state:
        cam_x = saved_state.get('cam_x', spawn_x)
        cam_y = saved_state.get('cam_y', spawn_y)
        cam_z = saved_state.get('cam_z', spawn_z)
        player_y = saved_state.get('player_y', cam_y)
        yaw = saved_state.get('yaw', 0.0)
        pitch = saved_state.get('pitch', 0.0)
    else:
        cam_x, cam_y, cam_z = spawn_x, spawn_y, spawn_z
        player_y = cam_y
        yaw = 0.0   
        pitch = 0.0 
    
    mouse_sensitivity = 0.15
    move_speed = 0.15
    player_radius = 0.5 # tamanho do "corpo" do jogador para colisão não ficar muito justa na parede

    pygame.font.init()
    
    script_path = os.path.dirname(os.path.abspath(__file__))

    script_path = os.path.dirname(script_path)

    font_path = os.path.join(script_path, 'Assets', 'Fonts', 'united-sans-reg-bold.otf')
    
    fonte_botao = pygame.font.Font(font_path, 28)
    fonte_titulo = pygame.font.SysFont('Arial', 72, bold=True)

    button_color = (0, 0, 0, 0)
    font_button_color = (95, 198, 139, 255)
    hover_button_color = (95, 198, 139, 150)

    title_pause = Title(
        screen_width // 2 - 300, screen_height // 2 - 200, 600, 100,
        "PAUSADO", fonte_titulo, bg_color=(0, 0, 0, 0),
        text_color=(255, 255, 255, 255), align="center"
    )

    caminho_alien = os.path.join(script_path, 'Assets', 'Characters', 'alien.png')
    alien_tex = load_alien_texture(caminho_alien)
    
    player_stamina = 100.0
    stamina_exhausted = False  # Flag anti-abuso: bloqueia corrida até recuperar 50

    # Restauração de estado adicional do save (stamina, alien, computadores)
    if saved_state:
        player_stamina = saved_state.get('player_stamina', 100.0)
        stamina_exhausted = saved_state.get('stamina_exhausted', False)
        
        # Restaura posição e estado do alien
        if 'alien_x' in saved_state:
            alien_ai.x = saved_state['alien_x']
            alien_ai.y = saved_state['alien_y']
            alien_ai.z = saved_state['alien_z']
            alien_ai.state = saved_state.get('alien_state', 'WANDERING')
            alien_ai.path_waypoints = []  # Limpa rota antiga, vai recalcular
        
        # Restaura quais computadores já foram resolvidos
        resolved_list = saved_state.get('computers_resolved', [])
        for i, is_resolved in enumerate(resolved_list):
            if i < len(computers_data):
                computers_data[i]['resolved'] = is_resolved

    running = True
    is_paused = False
    result_state = "MENU"
    esc_held = False

    def cb_continuar():
        nonlocal is_paused
        is_paused = False
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        pygame.mouse.get_rel()
        
    def cb_salvar_jogo():
        # Monta o dict com TODO o estado da fase
        level_data = {
            'planet_name': planet.name,
            # Jogador
            'cam_x': cam_x,
            'cam_y': cam_y,
            'cam_z': cam_z,
            'player_y': player_y,
            'yaw': yaw,
            'pitch': pitch,
            'player_stamina': player_stamina,
            'stamina_exhausted': stamina_exhausted,
            # Puzzle
            'puzzle_mapping': puzzle_mapping,
            # Computadores
            'computers_resolved': [c['resolved'] for c in computers_data],
            # Alien
            'alien_x': alien_ai.x,
            'alien_y': alien_ai.y,
            'alien_z': alien_ai.z,
            'alien_state': alien_ai.state,
        }
        save_manager.save_level_save(planet.name, level_data)
        # Atualiza o main_save para apontar para esta fase
        main = save_manager.load_main_save()
        save_manager.save_main_save(main.get('unlocked_planets', []), planet.name)
        # Retorna ao jogo logo em seguida para um fluxo suave
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

    btn_continue = Button(
        screen_width // 2 - 200, screen_height // 2 - 120, 450, 50, "CONTINUAR",
        fonte_botao, cb_continuar, base_color=button_color,
        hover_color=hover_button_color, text_color=font_button_color
    )
    btn_save_game = Button(
        screen_width // 2 - 200, screen_height // 2 - 50, 450, 50, "SALVAR JOGO",
        fonte_botao, cb_salvar_jogo, base_color=button_color,
        hover_color=hover_button_color, text_color=font_button_color
    )
    btn_load_game = Button(
        screen_width // 2 - 200, screen_height // 2 + 20, 450, 50, "CARREGAR JOGO",
        fonte_botao, cb_carregar_jogo, base_color=button_color,
        hover_color=hover_button_color, text_color=font_button_color
    )
    btn_back_menu = Button(
        screen_width // 2 - 200, screen_height // 2 + 90, 450, 50, "SAIR PARA SELEÇÃO DE PLANETAS",
        fonte_botao, cb_voltar_menu, base_color=button_color,
        hover_color=hover_button_color, text_color=font_button_color
    )
    btn_exit_desktop = Button(
        screen_width // 2 - 200, screen_height // 2 + 160, 450, 50, "SAIR PARA ÁREA DE TRABALHO",
        fonte_botao, cb_sair_desktop, base_color=button_color,
        hover_color=hover_button_color, text_color=font_button_color
    )

    while running:
        # Verifica se o jogador está perto de algum computador
        near_comp = None
        for comp in computers_data:
            dist_xz = math.hypot(cam_x - comp['x'], cam_z - comp['z'])
            # cam_y é a altura dos olhos, comp['y'] + 2.0 é o centro aproximado do monitor
            dist_y = abs(cam_y - (comp['y'] + 2.0))
            
            # Só permite interação se estiver perto no plano E no mesmo andar (dist_y < 2.0)
            if dist_xz < 2.5 and dist_y < 2.0:
                near_comp = comp
                break

        now = pygame.time.get_ticks()

        keys_raw = pygame.key.get_pressed()
        
        if (keys_raw[K_ESCAPE] or keys_raw[K_p]) and not esc_held:
            esc_held = True
            if interacting_comp:
                interacting_comp = None # Sai do PC
                pygame.mouse.set_visible(False)
                pygame.event.set_grab(True)
            else:
                if is_paused:
                    cb_continuar()
                else:
                    is_paused = True
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
        elif not (keys_raw[K_ESCAPE] or keys_raw[K_p]):
            esc_held = False

        # leitor de eventos
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
                
            if is_paused:
                btn_continue.handle_event(event)
                btn_save_game.handle_event(event)
                btn_load_game.handle_event(event)
                btn_back_menu.handle_event(event)
                btn_exit_desktop.handle_event(event)

            if event.type == KEYDOWN:
                if interacting_comp:
                    if event.key == K_BACKSPACE:
                        interacting_comp['current_input'] = interacting_comp['current_input'][:-1]
                    elif event.key == K_RETURN or event.key == K_KP_ENTER:
                        # Valida a senha
                        if interacting_comp['current_input'] == interacting_comp['expected'] or interacting_comp['current_input'] == '@':
                            interacting_comp['resolved'] = True
                            alien_ai.trigger_hunt(interacting_comp['x'], interacting_comp['y'] + 2.0, interacting_comp['z'])
                            interacting_comp = None # Fecha a tela em caso de sucesso
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                        else:
                            # Errou! Pisca a tela de vermelho por 300ms e apaga o input
                            error_blink_timer = now + 300
                            interacting_comp['current_input'] = ""
                            alien_ai.trigger_hunt(interacting_comp['x'], interacting_comp['y'] + 2.0, interacting_comp['z'])
                    else:
                        # captura qualquer letra ou número, além do cheat '@'
                        char_digitado = event.unicode.upper()
                        
                        if char_digitado.isalnum() or char_digitado == '@':
                            if len(interacting_comp['current_input']) < len(interacting_comp['expected']) or char_digitado == '@':
                                interacting_comp['current_input'] += char_digitado

                else:
                    if event.key == K_e and near_comp and not near_comp['resolved']: 
                        if not is_paused: 
                            # Abre a interface do computador
                            interacting_comp = near_comp
                            interacting_comp['current_input'] = ""
                            pygame.mouse.set_visible(True)
                            pygame.event.set_grab(False)

                    elif is_paused and event.key == K_q: 
                        running = False # encerra o loop e volta pro Hub
        
        if is_paused:
            mouse_pos = pygame.mouse.get_pos()
            btn_continue.check_hover(mouse_pos)
            btn_save_game.check_hover(mouse_pos)
            btn_load_game.check_hover(mouse_pos)
            btn_back_menu.check_hover(mouse_pos)
            btn_exit_desktop.check_hover(mouse_pos)

        if not is_paused and not interacting_comp:
            # movimento do mouse na câmera
            mouse_dx, mouse_dy = pygame.mouse.get_rel()
            yaw += mouse_dx * mouse_sensitivity
            pitch += mouse_dy * mouse_sensitivity
            
            if pitch > 89.0: pitch = 89.0
            if pitch < -89.0: pitch = -89.0

            # movimento do teclado e colisão
            keys = pygame.key.get_pressed()
            yaw_rad = math.radians(yaw)
            
            # vetores de direção matemática
            front_x = math.sin(yaw_rad)
            front_z = -math.cos(yaw_rad)
            right_x = math.cos(yaw_rad)
            right_z = math.sin(yaw_rad)

            # variáveis temporárias para testar a colisão antes de mover a câmera oficial
            next_x = cam_x
            next_z = cam_z

            # Mecânica anti-abuso de stamina:
            # Se a stamina chegar a 0, bloqueia corrida até recuperar 50
            if player_stamina <= 0:
                stamina_exhausted = True
            if stamina_exhausted and player_stamina >= 50:
                stamina_exhausted = False
            
            if keys[K_LSHIFT] and player_stamina > 0 and not stamina_exhausted:
                move_speed = 0.28 # velocidade de Corrida
                player_stamina = max(0.0, player_stamina - 0.6)
            else:
                move_speed = 0.15 # caminhada normal
                player_stamina = min(100.0, player_stamina + 0.15)

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

            # verificação de colisão eixo por eixo (permite andar encostado na parede)
            # testa o eixo X
            if not is_wall(next_x + (player_radius if next_x > cam_x else -player_radius), player_y, cam_z, collision_map):
                cam_x = next_x
                
            # testa o eixo Z
            if not is_wall(cam_x, player_y, next_z + (player_radius if next_z > cam_z else -player_radius), collision_map):
                cam_z = next_z

            # aplicação da lógica usada nas escadas e na gravidade
            player_y = get_target_y(cam_x, player_y, cam_z, current_map)
            
            # a câmera visual persegue a física real suavemente (cálculos ficam divididos da visão)
            cam_y += (player_y - cam_y) * 0.15

            alien_ai.update(cam_x, player_y, cam_z, collision_map)

            # --- GAME OVER: Alien encostou no jogador ---
            dist_alien = math.hypot(cam_x - alien_ai.x, cam_z - alien_ai.z)
            if dist_alien < 2.0 and abs(player_y - alien_ai.y) < 3.0:
                result_state = "loss"
                running = False

        # renderização
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        glRotatef(pitch, 1, 0, 0) 
        glRotatef(yaw, 0, 1, 0)   
        glTranslatef(-cam_x, -cam_y, -cam_z)

        # percorre a matriz 3D de layout do mapa
        for y_index, andar in enumerate(current_map):
            for z_index, linha in enumerate(andar):
                for x_index, char in enumerate(linha):
                    
                    # ignora espaço vazio
                    if char == ' ':
                        continue

                    block_x = x_index * BLOCK_SIZE
                    block_y = y_index * WALL_HEIGHT
                    block_z = z_index * BLOCK_SIZE

                    # renderização do chão
                    # mas se não houver uma rampa no bloco exatamente abaixo
                    if not has_ramp_below(y_index, z_index, x_index, current_map):
                        draw_floor_tile(block_x, block_y, block_z, BLOCK_SIZE)

                    # renderização da parede
                    if char == 'P':
                        draw_cube(block_x, block_y, block_z, BLOCK_SIZE, WALL_HEIGHT)

                    # TODO: draw_cube com textura transparente de vidro
                    elif char == 'V':
                        pass
                    
                    # renderização da escada
                    # passamos o 'char' (a direção) para orientar a escada
                    elif char in ['<', '>', '^', 'v']:
                        draw_u_stairs(block_x, block_y, block_z, BLOCK_SIZE, WALL_HEIGHT, char)

                    elif char in ['N', 'S', 'L', 'O']:
                        letra_secreta = puzzle_mapping[char]
                        draw_graffiti_cube(block_x, block_y, block_z, char, letra_secreta)

        for comp in computers_data:
            # Se resolvido fica verde, senão azul
            tela_cor = (0.0, 0.8, 0.2) if comp['resolved'] else (0.0, 0.0, 0.6)
            draw_computer(comp['x'], comp['y'], comp['z'], 4.0, 4.0, screen_color=tela_cor)

        draw_billboard_alien(alien_ai.x, alien_ai.y - 2.0, alien_ai.z, alien_tex, 4.0, alien_ai.is_flipped, yaw)

        # --- RENDERIZAÇÃO 2D (HUD E UI DO PC) ---
        prepare_2d(screen_width, screen_height)
        
        # 1. HUD: Rastreador de Computadores (Canto Superior Esquerdo)
        computadores_resolvidos = sum(1 for c in computers_data if c['resolved'])
        total_computadores = len(computers_data)

        if total_computadores > 0 and computadores_resolvidos == total_computadores:
            result_state = "win"
            running = False
        
        hud_surface = hud_font.render(f"Computadores acessados: {computadores_resolvidos}/{total_computadores}", True, (240, 240, 240))
        hud_data = pygame.image.tostring(hud_surface, "RGBA", True)
        hud_w, hud_h = hud_surface.get_size()
        
        # Cor da stamina: vermelho se exausta, azul claro se normal
        stamina_color = (255, 80, 80) if stamina_exhausted else (130, 200, 255)
        stamina_surface = hud_font.render(f"Stamina: {int(player_stamina)}/100", True, stamina_color)
        stamina_data = pygame.image.tostring(stamina_surface, "RGBA", True)
        stam_w, stam_h = stamina_surface.get_size()

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glRasterPos2f(20, 30) # Posição X, Y do texto
        glDrawPixels(hud_w, hud_h, GL_RGBA, GL_UNSIGNED_BYTE, hud_data)

        glRasterPos2f(20, 60) # Posição da stamina logo abaixo
        glDrawPixels(stam_w, stam_h, GL_RGBA, GL_UNSIGNED_BYTE, stamina_data)

        # 2. Prompt de Interação (Centro Inferior)
        if near_comp and not near_comp['resolved'] and not interacting_comp: 
            prompt_surf = hud_font.render("Aperte [E] para interagir", True, (255, 215, 120))
            p_w, p_h = prompt_surf.get_size()
            glRasterPos2f((screen_width - p_w) // 2, screen_height - 100)
            glDrawPixels(p_w, p_h, GL_RGBA, GL_UNSIGNED_BYTE, pygame.image.tostring(prompt_surf, "RGBA", True))

        # 3. TELA DO COMPUTADOR (Interface Hacker)
        if interacting_comp:
            # Dimensões da tela (60% da resolução do monitor)
            ui_w = screen_width * 0.6
            ui_h = screen_height * 0.6
            ui_x = (screen_width - ui_w) // 2
            ui_y = (screen_height - ui_h) // 2

            glDisable(GL_TEXTURE_2D)
            # Verifica o timer do piscar em vermelho
            if now < error_blink_timer:
                glColor4f(0.8, 0.1, 0.1, 0.95) # Fundo Vermelho de erro

            else:
                glColor4f(0.05, 0.15, 0.4, 0.95) # Fundo Azul terminal
                
            # Desenha a placa de fundo
            glBegin(GL_QUADS)
            glVertex2f(ui_x, ui_y); glVertex2f(ui_x + ui_w, ui_y)
            glVertex2f(ui_x + ui_w, ui_y + ui_h); glVertex2f(ui_x, ui_y + ui_h)
            glEnd()
            
            # Textos do Terminal
            seq_surf = comp_font_large.render(f"SEQUENCIA: {interacting_comp['sequence']}", True, (255, 255, 255))
            in_surf = comp_font_large.render(f"INPUT: {interacting_comp['current_input']}_", True, (100, 255, 100))
            
            # Desenha Sequência e Input centralizados dentro da placa
            glRasterPos2f(ui_x + 50, ui_y + ui_h * 0.3)
            glDrawPixels(*seq_surf.get_size(), GL_RGBA, GL_UNSIGNED_BYTE, pygame.image.tostring(seq_surf, "RGBA", True))
            
            glRasterPos2f(ui_x + 50, ui_y + ui_h * 0.6)
            glDrawPixels(*in_surf.get_size(), GL_RGBA, GL_UNSIGNED_BYTE, pygame.image.tostring(in_surf, "RGBA", True))
        
        if is_paused:
            glDisable(GL_TEXTURE_2D)
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
            btn_save_game.draw()
            btn_load_game.draw()
            btn_back_menu.draw()
            btn_exit_desktop.draw()

        prepare_3d()

        pygame.display.flip()
        clock.tick(FPS)

    return result_state