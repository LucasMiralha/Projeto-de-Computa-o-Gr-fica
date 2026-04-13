import os
import sys
import math
import pygame
import game_template
from OpenGL.GL import *
from OpenGL.GLU import *
from pygame.locals import *

# módulos core
from core.ui import Button, Title
from core.models import PlanetaData, load_planets
from core.graphics_utils import load_game_resources
import core.save_manager as save_manager
from core.renderer import (draw_ring, draw_background, draw_sphere, draw_fade_overlay,
                            draw_tooltip, start_opengl)

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


def main():
    # inicialização do pygame com buffer reduzido para tirar o lag de som
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    pygame.mixer.init() # Inicializa o módulo de som do pygame
    pygame.font.init() # inicializa o renderizador de fontes
    
    # obtém as informações do monitor atual
    screen_info = pygame.display.Info()
    screen_height = screen_info.current_h
    screen_width = screen_info.current_w

    screen = pygame.display.set_mode((screen_width, screen_height), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Tau Ceti Wars")

    script_path = os.path.dirname(os.path.abspath(__file__))

    # pega o diretório com o nome do arquivo json
    json_path = os.path.join(script_path, 'planetas.json')
    
    start_opengl(screen_height, screen_width)
    
    # essa função é responsável por carregar todos os recursos do jogo
    star_system, background_texture_id, ring_texture_id, font_path, music_path = load_game_resources(
        script_path,
        json_path,
        screen_width,
        screen_height
    )

    fonte_tooltip = pygame.font.SysFont(font_path, 24, bold=True)
    fonte_botao = pygame.font.Font(font_path, 28)
    fonte_titulo = pygame.font.SysFont('Arial', 72, bold=True)

    # carrega a música de ambiente
    music_path = os.path.join(script_path, 'Assets', 'Sounds', 'Deep Space Travel Ambience 3 (Menu).mp3')
    try:
        pygame.mixer.music.load(music_path)
        pygame.mixer.music.set_volume(0.6) # volume opcional para não estourar os ouvidos caso o arquivo seja alto
        pygame.mixer.music.play(-1) # -1 faz a música ficar rodando em loop
    except Exception as e:
        print(f"Aviso: Não foi possível carregar o som ambiente: {e}")
    
    # relógio para controle de fps
    clock = pygame.time.Clock()
    FPS = 60

    # --- LÓGICA DE ESTADOS E BOTÕES ---
    app_state = "MENU_INICIAL" # Estados: MENU_INICIAL, SISTEMA_SOLAR, PAUSE

    def cb_iniciar():
        nonlocal app_state
        app_state = "SISTEMA_SOLAR"

    def cb_sair_programa():
        pygame.quit()
        sys.exit()

    def cb_voltar_menu():
        nonlocal app_state
        app_state = "MENU_INICIAL"

    # Criando botões do Menu Inicial
    button_color = (0, 0, 0, 0)
    font_button_color = (95, 198, 139, 255)
    hover_button_color = (95, 198, 139, 150)

    # Inicialização do Título (PEP8)
    title_main = Title(
        screen_width // 2 - 300, screen_height // 2 - 250, 600, 100,
        "TAU CETI WARS", fonte_titulo, bg_color=(0, 0, 0, 0),
        text_color=(255, 255, 255, 0), align="center"
    )

    def cb_carregar_main():
        nonlocal app_state, transition_state, target_planet, saved_level_state
        data = save_manager.load_game()
        
        # Sincroniza estado global de planetas desbloqueados
        if data["unlocked_planets"]:
            for planet in star_system:
                if planet.name in data["unlocked_planets"]:
                    planet.is_unlocked = True
                    
        # Se tem nível salvo na memória, puxa fase inteira direto
        if data["level"]:
            target_name = data["level"]["planet_name"]
            for p in star_system:
                if p.name == target_name:
                    target_planet = p
                    break
            if target_planet:
                saved_level_state = data["level"]
                app_state = "SISTEMA_SOLAR"
                transition_state = "START_LEVEL"
        else:
            # Sem fase salva, só libera o sistema solar com progresso novo
            app_state = "SISTEMA_SOLAR"

    def cb_novo_jogo():
        nonlocal app_state
        # Reinicia o progresso da memória ativa para padrão antes de entrar
        for i, planet in enumerate(star_system):
            planet.is_unlocked = (i == 0)
        app_state = "SISTEMA_SOLAR"
        
    def cb_selecionar_planeta():
        nonlocal app_state
        # Entra direto no sistema solar com a memória atual
        app_state = "SISTEMA_SOLAR"

    btn_continue_main = Button(
        screen_width // 2 - 150, screen_height // 2 - 90, 300, 50, "CONTINUAR",
        fonte_botao, cb_carregar_main, base_color=button_color,
        hover_color=hover_button_color, text_color=font_button_color
    )
    btn_new_game = Button(
        screen_width // 2 - 150, screen_height // 2 - 20, 300, 50, "NOVO JOGO",
        fonte_botao, cb_novo_jogo, base_color=button_color,
        hover_color=hover_button_color, text_color=font_button_color
    )
    btn_select_planet = Button(
        screen_width // 2 - 200, screen_height // 2 + 50, 400, 50, "SELECIONAR PLANETA",
        fonte_botao, cb_selecionar_planeta, base_color=button_color,
        hover_color=hover_button_color, text_color=font_button_color
    )
    btn_exit_main = Button(
        screen_width // 2 - 100, screen_height // 2 + 120, 200, 50, "SAIR",
        fonte_botao, cb_sair_programa, base_color=button_color,
        hover_color=hover_button_color, text_color=font_button_color
    )

    # posições em que cada planeta vai ficar na cena
    planet_positions = [
        (-30.0, -10.0, 0.0), # Slot 1: fundo esquerda, mais baixo
        (-15.0,  -5.0, 0.0), # Slot 2
        (  0.0,   0.0, 0.0), # Slot 3: centro exato da tela
        ( 15.0,   5.0, 0.0), # Slot 4
        ( 30.0,  10.0, 0.0)  # Slot 5: frente direita, mais alto
    ]

    for i, planet in enumerate(star_system):
        if i < len(planet_positions):
            planet.pos_x, planet.pos_y, planet.pos_z = planet_positions[i]
        else:
            print(f"Aviso: Não há slots de posição suficientes para {planet.name}.")

    # progresso linear: desbloqueia apenas o primeiro planeta inicialmente
    if star_system:
        star_system[0].is_unlocked = True

    # variaveis de controle de camera
    cam_x, cam_y, cam_z = 0.0, 0.0, -50.0

    # velocidade da câmera durante a transição
    cam_speed = 0.025
    
    # variaveis da maquina de estados da transicao
    # estados: IDLE, PULLBACK, APPROACH, FADE_OUT, SPLASH, START_LEVEL
    transition_state = "IDLE" 
    target_planet = None
    saved_level_state = None
    fade_alpha = 0.0
    splash_timer = 0

    # variável de controle do loop de jogo
    running = True

    while running:

        mouse_pos = pygame.mouse.get_pos()
        
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                running = False
            
            # --- LÓGICA DE EVENTOS POR ESTADO ---
            if app_state == "MENU_INICIAL":
                btn_continue_main.handle_event(evento)
                btn_new_game.handle_event(evento)
                btn_select_planet.handle_event(evento)
                btn_exit_main.handle_event(evento)
            
            elif app_state == "SISTEMA_SOLAR":
                if evento.type == pygame.KEYDOWN:
                    if evento.key == pygame.K_ESCAPE:
                        app_state = "MENU_INICIAL" # Agora o ESC volta pro menu
                    
                    if evento.key == pygame.K_k:
                        for planet in star_system:
                            planet.is_unlocked = True
                        print("\nTodos os planetas foram desbloqueados")
                        # salva o global status
                        save_manager.save_global_state([p.name for p in star_system if p.is_unlocked])
                
                # detecta o clique do mouse no planeta
                if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
                    # so permite clicar se estiver livre (IDLE), tiver um planeta no foco, e ele for desbloqueado
                    if transition_state == "IDLE" and focused_planet and focused_planet.is_unlocked:
                        target_planet = focused_planet
                        transition_state = "PULLBACK"

        # --- ATUALIZAÇÃO DE HOVER DOS BOTÕES ---
        if app_state == "MENU_INICIAL":
            btn_continue_main.check_hover(mouse_pos)
            btn_new_game.check_hover(mouse_pos)
            btn_select_planet.check_hover(mouse_pos)
            btn_exit_main.check_hover(mouse_pos)

        # lógicas de estados de transição (SÓ OCORRE SE ESTIVER NO JOGO)
        if app_state == "SISTEMA_SOLAR":
            if transition_state == "PULLBACK":
                # Movimento simultâneo: Recua (Z) e Centraliza (X e Y) ao mesmo tempo.
                # Como usamos interpolação (cam_speed), isso cria um arco suave.
                target_z = -60.0
                target_x = -target_planet.pos_x
                target_y = -target_planet.pos_y
                
                cam_x += (target_x - cam_x) * cam_speed
                cam_y += (target_y - cam_y) * cam_speed
                cam_z += (target_z - cam_z) * cam_speed
                
                # quando estiver quase no ponto máximo de recuo e centralizado, vai para a frente
                if abs(cam_z - target_z) < 0.5 and abs(cam_x - target_x) < 0.5:
                    transition_state = "APPROACH"
                    
            elif transition_state == "APPROACH":
                # vai na direção do planeta alvo
                target_z = -target_planet.pos_z - (target_planet.size * 3.5) 
                cam_z += (target_z - cam_z) * cam_speed
                
                # verifica se a distância até o planeta é menor que 15 unidades
                distancia_restante = abs(cam_z - target_z)
                if distancia_restante < 15.0:
                    fade_alpha += 0.03 # um pouco mais rápido para fechar antes de bater
                    
                    # quando a tela fica 100% preta, passa para a arte
                    if fade_alpha >= 1.0:
                        fade_alpha = 1.0
                        transition_state = "SPLASH_FADE_IN"
                    
            elif transition_state == "SPLASH_FADE_IN":
                # reduz o alpha do quadrado preto para revelar a arte suavemente.
                fade_alpha -= 0.02
                
                if fade_alpha <= 0.0:
                    fade_alpha = 0.0
                    transition_state = "SPLASH_WAIT"
                    splash_timer = pygame.time.get_ticks() # começa a contar tempo de "loading" aqui
                    
            elif transition_state == "SPLASH_WAIT":
                # aguarda o tempo da arte da transição
                current_time = pygame.time.get_ticks()
                if current_time - splash_timer > 3000:
                    transition_state = "START_LEVEL"
                    
            elif transition_state == "START_LEVEL":
                print(f"\nIniciando fase: {target_planet.name}!")
                
                # Para a música ambiente ao entrar na fase
                pygame.mixer.music.fadeout(1000)
                
                # chama a fase escolhida injetando opcionalmente o load_state
                resultado_fase = game_template.start(target_planet, saved_state=saved_level_state)
                
                # retorno da fase para menu
                print(f"\nFase concluída: {target_planet.name}! ({resultado_fase})")
                
                # Reinicia a música ambiente do menu
                pygame.mixer.music.play(-1)
                
                if resultado_fase == "win": #{
                    # percorremos o sistema para encontrar o planeta que acabamos de vencer
                    for i in range(len(star_system)): #{
                        if star_system[i].name == target_planet.name: #{
                            # se existir um próximo planeta na lista, ele é desbloqueado
                            if i + 1 < len(star_system): #{
                                star_system[i + 1].is_unlocked = True
                                print(f"Sucesso! Próximo destino desbloqueado: {star_system[i + 1].name}")
                                save_manager.save_game_progress(star_system)
                            break
                
                # reseta todas as variáveis de visualização
                start_opengl(screen_height, screen_width)
                
                if resultado_fase == "LOAD_GAME":
                    cb_carregar_main()
                else:
                    app_state = "SISTEMA_SOLAR"
                    transition_state = "IDLE"
                    fade_alpha = 0.0
                    target_planet = None
                    cam_x, cam_y, cam_z = 0.0, 0.0, -50.0
                    saved_level_state = None
                
                # destrava o mouse
                pygame.mouse.set_visible(True)
                pygame.event.set_grab(False)

        # --- RENDERIZAÇÃO ---
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        if app_state == "MENU_INICIAL":
            # Agora exibe o fundo espacial também no menu principal
            if background_texture_id:
                draw_background(background_texture_id)
                
            prepare_2d(screen_width, screen_height)
            title_main.draw() # Desenha o título do jogo
            btn_continue_main.draw()
            btn_new_game.draw()
            btn_select_planet.draw()
            btn_exit_main.draw()
            prepare_3d()

        elif app_state == "SISTEMA_SOLAR":
            # Cor do espaço
            glClearColor(0, 0, 0, 1)

            # Desenha o fundo espacial
            if background_texture_id:
                draw_background(background_texture_id)

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity() 
            glTranslatef(cam_x, cam_y, cam_z) 

            modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
            projection = glGetDoublev(GL_PROJECTION_MATRIX)
            viewport = glGetIntegerv(GL_VIEWPORT)
            focused_planet = None

            for planet in star_system:
                planet.current_angle += planet.rotation_speed
                if planet.current_angle >= 360.0:
                    planet.current_angle -= 360.0

                if transition_state == "IDLE" and app_state == "SISTEMA_SOLAR":
                    try:
                        win_x, win_y, win_z = gluProject(planet.pos_x, planet.pos_y, planet.pos_z, modelview, projection, viewport)
                        x_limit, _, _ = gluProject(planet.pos_x + planet.size, planet.pos_y, planet.pos_z, modelview, projection, viewport)
                        screen_radius = abs(x_limit - win_x)
                        win_y_inverted = screen_height - win_y
                        distance = math.hypot(mouse_pos[0] - win_x, mouse_pos[1] - win_y_inverted)
                        if distance < screen_radius:
                            focused_planet = planet
                    except (ValueError, OpenGL.GLU.GLUerror):
                        pass 

                glPushMatrix() 
                glTranslatef(planet.pos_x, planet.pos_y, planet.pos_z) 
                glRotatef(-90.0, 1, 0, 0)
                glRotatef(planet.axis_tilt, 1, 0, 0) 
                if planet.has_rings:
                    draw_ring(planet.size * 1.2, planet.size * 1.9, ring_texture_id)
                glRotatef(planet.current_angle, 0, 0, 1)
                draw_sphere(planet.size, planet.color_or_texture, planet.texture_id)
                glPopMatrix() 

            # Desenha a Tooltip se não estiver pausado
            if focused_planet and transition_state == "IDLE" and app_state == "SISTEMA_SOLAR":
                if focused_planet.is_unlocked:
                    texto_ui, cor_texto = focused_planet.name, (255, 255, 255)
                else:
                    texto_ui, cor_texto = f"{focused_planet.name} (BLOQUEADO)", (255, 80, 80)
                draw_tooltip(texto_ui, mouse_pos[0], mouse_pos[1], screen_width, screen_height, fonte_tooltip, cor_texto)

            if transition_state in ["SPLASH_FADE_IN", "SPLASH_WAIT"]:
                if target_planet and target_planet.splash_texture_id:
                    draw_background(target_planet.splash_texture_id)

            if fade_alpha > 0.0:
                draw_fade_overlay(screen_width, screen_height, fade_alpha)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()