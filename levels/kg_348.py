import os
import pygame
import sys
import math
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

from core.renderer import draw_cube, draw_floor_tile, draw_computer, draw_door, draw_sphere
import core.ai as ai_module
from core.physics_engine import BLOCK_SIZE, WALL_HEIGHT, is_wall
from core.ui import Button, Title
import core.save_manager as save_manager
import copy

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

def init_opengl_fps(width, height):
    glViewport(0, 0, int(width), int(height))
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(75, (width / height), 0.1, 1000.0)
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)
    glDisable(GL_BLEND)

def start(planet, saved_state=None):
    screen_info = pygame.display.Info()
    screen_width = screen_info.current_w
    screen_height = screen_info.current_h
    
    pygame.display.set_mode((screen_width, screen_height), DOUBLEBUF | OPENGL | FULLSCREEN)
    init_opengl_fps(screen_width, screen_height)
    
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)
    
    clock = pygame.time.Clock()
    FPS = 60

    current_map = planet.layout
    
    cam_x, cam_y, cam_z = 0.0, 2.0, 0.0
    yaw, pitch = 0.0, 0.0
    # Precisamos ter player_y para o save_manager
    player_y = cam_y
    
    computers_data = []
    doors_data = []
    final_zone_data = None

    # encontra o '@' (spawn) varrendo a matriz 3D
    for y_index, andar in enumerate(current_map):
        for z_index, linha in enumerate(andar):
            for x_index, char in enumerate(linha):
                world_x = x_index * BLOCK_SIZE
                world_y = y_index * WALL_HEIGHT
                world_z = z_index * BLOCK_SIZE

                if char == '@':
                    cam_x = world_x
                    cam_y = world_y + 2.0
                    cam_z = world_z
                    player_y = cam_y
                elif char in ('M', 'B'):
                    is_broken = (char == 'B')
                    computers_data.append({
                        'x': world_x,
                        'y': world_y,
                        'z': world_z,
                        'grid_y': y_index,
                        'grid_z': z_index,
                        'grid_x': x_index,
                        'is_broken': is_broken
                    })
                elif char == 'F':
                    final_zone_data = {
                        'x': world_x,
                        'y': world_y,
                        'z': world_z,
                        'grid_y': y_index,
                        'grid_z': z_index,
                        'grid_x': x_index
                    }
                elif char == 'D':
                    doors_data.append({
                        'x': world_x,
                        'y': world_y,
                        'z': world_z,
                        'grid_y': y_index,
                        'grid_z': z_index,
                        'grid_x': x_index,
                        'is_open': False
                    })

    # As 2 portas mais próximas iniciam abertas
    doors_data.sort(key=lambda d: math.hypot(d['x'] - cam_x, d['z'] - cam_z))
    for i in range(min(2, len(doors_data))):
        doors_data[i]['is_open'] = True

    collision_map = copy.deepcopy(current_map)
    for y_index, andar in enumerate(collision_map):
        for z_index, linha in enumerate(andar):
            linha_list = list(linha)
            for x_index, char in enumerate(linha_list):
                if char == '@':
                    linha_list[x_index] = '.'
                elif char == 'F':
                    linha_list[x_index] = 'P' # Inicialmente trancada
            collision_map[y_index][z_index] = "".join(linha_list)
            
    def update_collision_map():
        for d in doors_data:
            linha = list(collision_map[d['grid_y']][d['grid_z']])
            linha[d['grid_x']] = '.' if d['is_open'] else 'P'
            collision_map[d['grid_y']][d['grid_z']] = "".join(linha)
            
    update_collision_map()

    if saved_state:
        cam_x = saved_state['cam_x']
        cam_y = saved_state['cam_y']
        cam_z = saved_state['cam_z']
        yaw = saved_state['yaw']
        pitch = saved_state['pitch']
        player_y = saved_state.get('player_y', cam_y)

    mouse_sensitivity = 0.15
    move_speed = 0.2
    player_radius = 0.5
    
    # --- UI DO PAUSE ---
    pygame.font.init()
    script_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
    
    hud_font = pygame.font.SysFont("consolas", 24, bold=True)

    running = True
    is_paused = False
    is_game_over = False
    result_state = "MENU"
    esc_held = False
    
    is_computer_ui_active = False
    active_doors = []
    near_comp_active = None
    terminal_title_font = pygame.font.SysFont("consolas", 48, bold=True)
    terminal_font = pygame.font.SysFont("consolas", 32, bold=True)
    
    fixed_computers = 0
    dev_mode = False
    ai_pos_x = 27 * BLOCK_SIZE
    ai_pos_z = 13 * BLOCK_SIZE
    ai_pos_y = 0.0
    ai_path = []
    ai_last_path_time = 0
    ai_state_timer = 0

    def cb_continuar():
        nonlocal is_paused
        is_paused = False
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        pygame.mouse.get_rel()
        
    def cb_salvar_jogo():
        save_manager.save_level_state(cam_x, cam_y, cam_z, player_y, yaw, pitch, planet.name)
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

    def cb_restart_level():
        nonlocal running, result_state
        result_state = "RESTART"
        running = False
        
    title_game_over = Title(
        screen_width // 2 - 300, screen_height // 2 - 200, 600, 100,
        "VOCÊ MORREU", fonte_titulo, bg_color=(0, 0, 0, 0),
        text_color=(255, 50, 50, 255), align="center"
    )
    btn_restart_go = Button(
        screen_width // 2 - 200, screen_height // 2 - 50, 450, 50, "TENTAR DE NOVO",
        fonte_botao, cb_restart_level, base_color=button_color,
        hover_color=hover_button_color, text_color=font_button_color
    )

    while running:
        keys = pygame.key.get_pressed()
        
        near_comp = None
        for comp in computers_data:
            dist_xz = math.hypot(cam_x - comp['x'], cam_z - comp['z'])
            dist_y = abs(cam_y - (comp['y'] + 2.0))
            if dist_xz < 3.0 and dist_y < 2.0:
                near_comp = comp
                break
        
        if not is_game_over:
            if (keys[K_ESCAPE] or keys[K_p]) and not esc_held:
                esc_held = True
                if is_computer_ui_active:
                    is_computer_ui_active = False
                    pygame.mouse.set_visible(False)
                    pygame.event.set_grab(True)
                    pygame.mouse.get_rel()
                elif is_paused:
                    cb_continuar()
                else:
                    is_paused = True
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
            elif not (keys[K_ESCAPE] or keys[K_p]):
                esc_held = False
            
        mouse_pos = pygame.mouse.get_pos()
        if is_game_over:
            btn_restart_go.check_hover(mouse_pos)
            btn_load_game.check_hover(mouse_pos)
            btn_back_menu.check_hover(mouse_pos)
            btn_exit_desktop.check_hover(mouse_pos)
        elif is_paused:
            btn_continue.check_hover(mouse_pos)
            btn_save_game.check_hover(mouse_pos)
            btn_load_game.check_hover(mouse_pos)
            btn_back_menu.check_hover(mouse_pos)
            btn_exit_desktop.check_hover(mouse_pos)
            
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
                
            if is_game_over:
                btn_restart_go.handle_event(event)
                btn_load_game.handle_event(event)
                btn_back_menu.handle_event(event)
                btn_exit_desktop.handle_event(event)
            elif is_paused:
                btn_continue.handle_event(event)
                btn_save_game.handle_event(event)
                btn_load_game.handle_event(event)
                btn_back_menu.handle_event(event)
                btn_exit_desktop.handle_event(event)
                
            if event.type == KEYDOWN:
                if event.key == K_o:
                    dev_mode = not dev_mode
                    print(f"DEV MODE: {'ON - Imortalidade' if dev_mode else 'OFF'}")
                if event.key == K_p:
                    if is_paused:
                        cb_continuar()
                    else:
                        is_paused = True
                        pygame.mouse.set_visible(True)
                        pygame.event.set_grab(False)
                elif is_paused and event.key == K_q:
                    running = False
                elif not is_paused and event.key == K_e:
                    if is_computer_ui_active:
                        is_computer_ui_active = False
                        pygame.mouse.get_rel()
                    elif near_comp and len(doors_data) > 0:
                        room_doors = []
                        for d in doors_data:
                            if d['grid_y'] != near_comp['grid_y']:
                                continue
                            if d['grid_x'] == near_comp['grid_x'] or d['grid_z'] == near_comp['grid_z']:
                                has_wall = False
                                if d['grid_x'] == near_comp['grid_x']:
                                    z_min = min(d['grid_z'], near_comp['grid_z'])
                                    z_max = max(d['grid_z'], near_comp['grid_z'])
                                    for z in range(z_min + 1, z_max):
                                        if current_map[d['grid_y']][z][d['grid_x']] in ['P', 'F', 'D']:
                                            has_wall = True
                                            break
                                else:
                                    x_min = min(d['grid_x'], near_comp['grid_x'])
                                    x_max = max(d['grid_x'], near_comp['grid_x'])
                                    for x in range(x_min + 1, x_max):
                                        if current_map[d['grid_y']][d['grid_z']][x] in ['P', 'F', 'D']:
                                            has_wall = True
                                            break
                                if not has_wall:
                                    room_doors.append(d)
                        if room_doors:
                            room_doors.sort(key=lambda d: (d['grid_z'], d['grid_x']))
                            active_doors = room_doors
                            near_comp_active = near_comp
                            is_computer_ui_active = True
                elif is_computer_ui_active and event.key >= K_1 and event.key <= K_9:
                    if near_comp_active.get('is_broken', False):
                        if event.key == K_1:
                            near_comp_active['is_broken'] = False
                            fixed_computers += 1
                            if fixed_computers >= 3 and final_zone_data:
                                # Abre a passagem pro jogador
                                l = list(collision_map[final_zone_data['grid_y']][final_zone_data['grid_z']])
                                l[final_zone_data['grid_x']] = '.'
                                collision_map[final_zone_data['grid_y']][final_zone_data['grid_z']] = "".join(l)
                            is_computer_ui_active = False
                            pygame.mouse.get_rel()
                    else:
                        idx = event.key - K_1
                        if idx < len(active_doors):
                            for d in active_doors:
                                d['is_open'] = False
                            active_doors[idx]['is_open'] = True
                            update_collision_map()
                            try:
                                pygame.mixer.Sound(os.path.join(script_path, 'Assets', 'Sounds', 'opening metal door.mp3')).play()
                            except Exception as e:
                                print(f"Erro no som da porta: {e}")
        
        if is_paused:
            mouse_pos = pygame.mouse.get_pos()
            btn_continue.check_hover(mouse_pos)
            btn_save_game.check_hover(mouse_pos)
            btn_load_game.check_hover(mouse_pos)
            btn_back_menu.check_hover(mouse_pos)
            btn_exit_desktop.check_hover(mouse_pos)
            
        if not is_paused and not is_computer_ui_active and not is_game_over:
            mouse_dx, mouse_dy = pygame.mouse.get_rel()
            yaw += mouse_dx * mouse_sensitivity
            pitch += mouse_dy * mouse_sensitivity
            
            if pitch > 89.0: pitch = 89.0
            if pitch < -89.0: pitch = -89.0
            
            yaw_rad = math.radians(yaw)
            
            front_x = math.sin(yaw_rad)
            front_z = -math.cos(yaw_rad)
            right_x = math.cos(yaw_rad)
            right_z = math.sin(yaw_rad)
            
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
                
            if not is_wall(next_x + (player_radius if next_x > cam_x else -player_radius), cam_y, cam_z, collision_map):
                cam_x = next_x
                
            if not is_wall(cam_x, cam_y, next_z + (player_radius if next_z > cam_z else -player_radius), collision_map):
                cam_z = next_z
                
            if fixed_computers >= 3 and final_zone_data:
                if math.hypot(cam_x - final_zone_data['x'], cam_z - final_zone_data['z']) < 2.0:
                    print("- VOCE CONCLUIU A MISSAO COM SUCESSO -")
                    return "win"
                
            current_time = pygame.time.get_ticks()
            if fixed_computers > 0:
                ai_profile = ai_module.get_creature_profile(fixed_computers)
                
                dist_to_p = math.hypot(cam_x - ai_pos_x, cam_z - ai_pos_z)
                
                # Efeito Xenomorph (Teleporte Alien Isolation)
                # Só se teletransporta se estiver há um tempo sem nenhum caminho viável físico pro jogador (Duto de ar)
                if len(ai_path) == 0 and ai_profile['state'] != "Adormecida":
                    if ai_state_timer == 0:
                        ai_state_timer = current_time + 15000 # 15 segundos do usuario
                    elif current_time > ai_state_timer:
                        # Alien Isolation: Tenta nascer num corredor andável na sua área isolada atual!
                        # ai_map impede que ele nasça atrás de outra porta trancada em relação a você.
                        # Usa um mapa temporal atualizado antes do timer, mas que resolvemos regerando aqui se for None:
                        spawn_map = [r.replace('P', '#').replace('F', '#') for r in collision_map[0]]
                        spawn_point = ai_module.get_alien_isolation_spawn(spawn_map, (cam_x, cam_z))
                        if spawn_point:
                            ai_pos_x, ai_pos_z = spawn_point
                        else:
                            # Manda o Perseguidor de volta pras profundezas se a sala for minúscula e não tiver spawn longe
                            ai_pos_x, ai_pos_z = 27 * BLOCK_SIZE, 13 * BLOCK_SIZE
                        ai_state_timer = 0
                        ai_path = [] # Reset explícito
                else:
                    ai_state_timer = 0
                    
                # Pathfinding
                if current_time - ai_last_path_time > ai_profile['path_refresh_ms']:
                    # Alien Isolation override: Ignora a miopia da classe base. A IA tem faro global!
                    # Traduz as paredes ('P', 'F') para '#' apenas para os olhos da IA do módulo base
                    ai_map = [r.replace('P', '#').replace('F', '#') for r in collision_map[0]]
                    
                    target_px, target_pz = cam_x, cam_z
                    # Estabilidade: Se o arredondamento cair numa parede (jogador "abraçando" a parede), tenta o adjacente
                    tgt_r, tgt_c = ai_module.world_to_cell(target_px, target_pz)
                    if 0 <= tgt_r < len(ai_map) and 0 <= tgt_c < len(ai_map[0]) and ai_map[tgt_r][tgt_c] == '#':
                        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                            nr, nc = tgt_r+dr, tgt_c+dc
                            if 0 <= nr < len(ai_map) and 0 <= nc < len(ai_map[0]) and ai_map[nr][nc] != '#':
                                target_px, target_pz = ai_module.cell_to_world(nr, nc)
                                break
                                
                    ai_path = ai_module.find_path(ai_map, (ai_pos_x, ai_pos_z), (target_px, target_pz))
                    ai_last_path_time = current_time

                # Move
                if len(ai_path) > 1:
                    target_row, target_col = ai_path[1]
                    target_x, target_z = ai_module.cell_to_world(target_row, target_col)
                    dx = target_x - ai_pos_x
                    dz = target_z - ai_pos_z
                    dist = math.hypot(dx, dz)
                    if dist > 0:
                        # Substituindo a velocidade veloz da classe base por uma override mais tática do Level
                        kg_speed_override = 0.035 if fixed_computers <= 1 else (0.042 if fixed_computers == 2 else 0.048)
                        move_spd = kg_speed_override * BLOCK_SIZE # Player speed é ~0.8 por bloco
                        move_dist = min(dist, move_spd)
                        ai_pos_x += (dx / dist) * move_dist
                        ai_pos_z += (dz / dist) * move_dist
                        if dist < move_spd:
                            ai_path.pop(0)

                # Game Over Check
                if math.hypot(cam_x - ai_pos_x, cam_z - ai_pos_z) < 1.0:
                    if not dev_mode and not is_game_over:
                        print("- VOCE FOI PEGO PELO PERSEGUIDOR -")
                        try:
                            pygame.mixer.Sound(os.path.join(script_path, 'Assets', 'Sounds', 'ai-01.mp3')).play()
                        except Exception as e:
                            print(f"Erro no som: {e}")
                        is_game_over = True
                        pygame.mouse.set_visible(True)
                        pygame.event.set_grab(False)
                        
            if is_game_over or is_paused:
                pass # Impede mouse_get_rel no jogo
            else:
                pass # Eventos de mouse já moviam a camera antes
            
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        glRotatef(pitch, 1, 0, 0)
        glRotatef(yaw, 0, 1, 0)
        glTranslatef(-cam_x, -cam_y, -cam_z)
        
        for y_index, andar in enumerate(current_map):
            for z_index, linha in enumerate(andar):
                for x_index, char in enumerate(linha):
                    if char == ' ': continue
                    
                    block_x = x_index * BLOCK_SIZE
                    block_y = y_index * WALL_HEIGHT
                    block_z = z_index * BLOCK_SIZE
                    
                    if char in ('P', 'D', 'F'):
                        if char == 'P':
                            draw_cube(block_x, block_y, block_z, BLOCK_SIZE, WALL_HEIGHT, color=(0.2, 0.4, 0.6))
                        elif char == 'F':
                            if fixed_computers >= 3:
                                draw_door(block_x, block_y, block_z, 4.0, 4.0, color=(0.2, 0.8, 0.2)) # Porta Livre
                            else:
                                draw_door(block_x, block_y, block_z, 4.0, 4.0, color=(0.8, 0.2, 0.2)) # Porta Trancada
                        else:
                            pass
                    
                    if char != 'P':
                        draw_floor_tile(block_x, block_y, block_z, BLOCK_SIZE, color=(0.1, 0.2, 0.3))
        
        for comp in computers_data:
            c_color = (0.8, 0.8, 0.1) if comp.get('is_broken', False) else (0.8, 0.1, 0.1)
            draw_computer(comp['x'], comp['y'], comp['z'], 4.0, 4.0, screen_color=c_color)

        for d in doors_data:
            if not d['is_open']:
                draw_door(d['x'], d['y'], d['z'], 4.0, 4.0, color=(0.4, 0.55, 0.6))
                
        # Desenha IA
        if fixed_computers > 0:
            glPushMatrix()
            glTranslatef(ai_pos_x, ai_pos_y + 1.5, ai_pos_z)
            draw_sphere(1.5, "#150020", None)
            glPopMatrix()

        if is_game_over:
            prepare_2d(screen_width, screen_height)
            glDisable(GL_TEXTURE_2D)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            # Fundo avermelhado de sangue
            glColor4f(0.5, 0, 0, 0.4)
            glBegin(GL_QUADS)
            glVertex2f(0, 0)
            glVertex2f(screen_width, 0)
            glVertex2f(screen_width, screen_height)
            glVertex2f(0, screen_height)
            glEnd()
            
            glEnable(GL_TEXTURE_2D)
            title_game_over.draw()
            btn_restart_go.draw()
            btn_load_game.draw()
            btn_back_menu.draw()
            btn_exit_desktop.draw()

            prepare_3d()
            
        elif is_paused:
            prepare_2d(screen_width, screen_height)
            
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
            
        if is_computer_ui_active:
            prepare_2d(screen_width, screen_height)
            glDisable(GL_TEXTURE_2D)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            # Fundo Painel HUD do Computador
            glColor4f(0, 0.05, 0, 0.9)
            glBegin(GL_QUADS)
            glVertex2f(screen_width // 2 - 400, screen_height // 2 - 300)
            glVertex2f(screen_width // 2 + 400, screen_height // 2 - 300)
            glVertex2f(screen_width // 2 + 400, screen_height // 2 + 300)
            glVertex2f(screen_width // 2 - 400, screen_height // 2 + 300)
            glEnd()
            
            # Borda do Terminal
            glColor4f(0, 1.0, 0, 0.5)
            glLineWidth(3.0)
            glBegin(GL_LINE_LOOP)
            glVertex2f(screen_width // 2 - 400, screen_height // 2 - 300)
            glVertex2f(screen_width // 2 + 400, screen_height // 2 - 300)
            glVertex2f(screen_width // 2 + 400, screen_height // 2 + 300)
            glVertex2f(screen_width // 2 - 400, screen_height // 2 + 300)
            glEnd()
            
            if near_comp_active.get('is_broken', False):
                title_surf = terminal_title_font.render("SISTEMA CORROMPIDO", True, (255, 100, 0))
                tw, th = title_surf.get_size()
                glRasterPos2f((screen_width - tw) // 2, screen_height // 2 - 250)
                glDrawPixels(tw, th, GL_RGBA, GL_UNSIGNED_BYTE, pygame.image.tostring(title_surf, "RGBA", True))
                
                linha_surf = terminal_font.render("[1] EXECUTAR REPARO DO SISTEMA", True, (255, 255, 0))
                lw, lh = linha_surf.get_size()
                glRasterPos2f((screen_width - lw) // 2, screen_height // 2)
                glDrawPixels(lw, lh, GL_RGBA, GL_UNSIGNED_BYTE, pygame.image.tostring(linha_surf, "RGBA", True))
                
                tip_surf = terminal_font.render("[ESC/E] ABANDONAR TERMINAL", True, (150, 150, 150))
                tip_w, tip_h = tip_surf.get_size()
                glRasterPos2f((screen_width - tip_w) // 2, screen_height // 2 + 250)
                glDrawPixels(tip_w, tip_h, GL_RGBA, GL_UNSIGNED_BYTE, pygame.image.tostring(tip_surf, "RGBA", True))
            else:
                title_surf = terminal_title_font.render("SISTEMA DE CONTROLE", True, (0, 255, 0))
                tw, th = title_surf.get_size()
                glRasterPos2f((screen_width - tw) // 2, screen_height // 2 - 250)
                glDrawPixels(tw, th, GL_RGBA, GL_UNSIGNED_BYTE, pygame.image.tostring(title_surf, "RGBA", True))
                
                start_y = screen_height // 2 - 120
                for i, d in enumerate(active_doors):
                    dir_name = "PORTA DESCONHECIDA"
                    if d['grid_z'] < near_comp_active['grid_z']: dir_name = "PORTA NORTE"
                    elif d['grid_z'] > near_comp_active['grid_z']: dir_name = "PORTA SUL "
                    elif d['grid_x'] > near_comp_active['grid_x']: dir_name = "PORTA LESTE"
                    elif d['grid_x'] < near_comp_active['grid_x']: dir_name = "PORTA OESTE"
                    
                    status_txt = "[ ABERTA  ]" if d['is_open'] else "[ FECHADA ]"
                    color = (50, 255, 50) if d['is_open'] else (255, 50, 50)
                    
                    linha_surf = terminal_font.render(f"[{i+1}] {dir_name}   {status_txt}", True, color)
                    lw, lh = linha_surf.get_size()
                    glRasterPos2f(screen_width // 2 - 250, start_y + i * 50)
                    glDrawPixels(lw, lh, GL_RGBA, GL_UNSIGNED_BYTE, pygame.image.tostring(linha_surf, "RGBA", True))
                    
                tip_surf = terminal_font.render("[ESC/E] SAIR DO TERMINAL   [1-9] SELECIONAR", True, (100, 200, 100))
                tip_w, tip_h = tip_surf.get_size()
                glRasterPos2f((screen_width - tip_w) // 2, screen_height // 2 + 250)
                glDrawPixels(tip_w, tip_h, GL_RGBA, GL_UNSIGNED_BYTE, pygame.image.tostring(tip_surf, "RGBA", True))
                
            prepare_3d()
            
        elif not is_paused and near_comp:
            prepare_2d(screen_width, screen_height)
            prompt_surf = hud_font.render("Aperte [E] para hackear portas", True, (255, 215, 120))
            p_w, p_h = prompt_surf.get_size()
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glRasterPos2f((screen_width - p_w) // 2, screen_height - 100)
            glDrawPixels(p_w, p_h, GL_RGBA, GL_UNSIGNED_BYTE, pygame.image.tostring(prompt_surf, "RGBA", True))
            prepare_3d()
            
        pygame.display.flip()
        clock.tick(FPS)
        
    return result_state
