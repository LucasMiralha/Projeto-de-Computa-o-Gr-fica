import pygame
import math
from OpenGL.GL import *
from OpenGL.GLU import *
from core.graphics_utils import hex_to_rgb
from core.physics_engine import *


def draw_textured_floor_tile(x, y, z, size, texture_id=None, color=(0.1, 0.1, 0.1), uv_scale=1.0):
    if texture_id is None:
        draw_floor_tile(x, y, z, size, color=color)
        return

    half = size / 2.0
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor3f(1.0, 1.0, 1.0)
    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 0.0); glVertex3f(x - half, y, z - half)
    glTexCoord2f(0.0, uv_scale); glVertex3f(x - half, y, z + half)
    glTexCoord2f(uv_scale, uv_scale); glVertex3f(x + half, y, z + half)
    glTexCoord2f(uv_scale, 0.0); glVertex3f(x + half, y, z - half)
    glEnd()
    glDisable(GL_TEXTURE_2D)


def draw_textured_cube(x, y, z, size, height, texture_id=None, color=(0.15, 0.2, 0.15), uv_scale=1.0):
    if texture_id is None:
        draw_cube(x, y, z, size, height, color=color)
        return

    half = size / 2.0
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor3f(1.0, 1.0, 1.0)
    glBegin(GL_QUADS)

    # frente
    glTexCoord2f(0.0, 0.0); glVertex3f(x - half, y, z + half)
    glTexCoord2f(uv_scale, 0.0); glVertex3f(x + half, y, z + half)
    glTexCoord2f(uv_scale, uv_scale); glVertex3f(x + half, y + height, z + half)
    glTexCoord2f(0.0, uv_scale); glVertex3f(x - half, y + height, z + half)

    # tras
    glTexCoord2f(0.0, 0.0); glVertex3f(x + half, y, z - half)
    glTexCoord2f(uv_scale, 0.0); glVertex3f(x - half, y, z - half)
    glTexCoord2f(uv_scale, uv_scale); glVertex3f(x - half, y + height, z - half)
    glTexCoord2f(0.0, uv_scale); glVertex3f(x + half, y + height, z - half)

    # esquerda
    glTexCoord2f(0.0, 0.0); glVertex3f(x - half, y, z - half)
    glTexCoord2f(uv_scale, 0.0); glVertex3f(x - half, y, z + half)
    glTexCoord2f(uv_scale, uv_scale); glVertex3f(x - half, y + height, z + half)
    glTexCoord2f(0.0, uv_scale); glVertex3f(x - half, y + height, z - half)

    # direita
    glTexCoord2f(0.0, 0.0); glVertex3f(x + half, y, z + half)
    glTexCoord2f(uv_scale, 0.0); glVertex3f(x + half, y, z - half)
    glTexCoord2f(uv_scale, uv_scale); glVertex3f(x + half, y + height, z - half)
    glTexCoord2f(0.0, uv_scale); glVertex3f(x + half, y + height, z + half)

    glEnd()
    glDisable(GL_TEXTURE_2D)

def draw_ring(internal_radius, external_radius, texture_id):
    # gerando malha com furo no meio
    quadric = gluNewQuadric()
    
    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        gluQuadricTexture(quadric, GL_TRUE)
        # ultimo valor em 1 para garantir canal alpha (transparência)
        glColor4f(1.0, 1.0, 1.0, 1.0) 
        
    # parâmetros: quadric, raio interno, raio externo, fatias, anéis_concêntricos
    # 64 fatias deixam o anel bem redondinho O
    gluDisk(quadric, internal_radius, external_radius, 64, 1)
    
    gluDeleteQuadric(quadric)
    
    if texture_id is not None:
        glDisable(GL_TEXTURE_2D)


def draw_sphere(radius, hex_color, texture_id):
    # cria uma esfera
    quadric = gluNewQuadric()
    
    # definindo a cor
    if texture_id is not None:
        # liga o modo de textura 2D
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        gluQuadricTexture(quadric, GL_TRUE)
        # branco para não alterar a cor da textura
        glColor3f(1.0, 1.0, 1.0)
    else:
        # sem textura, pinta cor sólida
        glDisable(GL_TEXTURE_2D)
        if hex_color.startswith('#'):
            r, g, b = hex_to_rgb(hex_color)
            glColor3f(r, g, b)

    # parâmetros: quadric, raio, latitude, longitude
    # uma esfera com 32 divisões horizontais e verticais fica minimamente suave
    gluSphere(quadric, radius, 32, 32)
    
    gluDeleteQuadric(quadric)
    # dedabilita para próximo carregamento
    glDisable(GL_TEXTURE_2D)


def draw_tooltip(text, mouse_x, mouse_y, width, height, font, text_color):
    # renderiza o texto no PyGame (Branco com fundo cinza escuro)
    text_surface = font.render(f"  {text}  ", True, text_color, (40, 40, 40))
    text_width, text_height = text_surface.get_size()
    dados_imagem = pygame.image.tostring(text_surface, "RGBA", True)

    # gera uma textura temporária
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, text_width, text_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, dados_imagem)

    # entra no modo 2D (NDC)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # desliga a profundidade para desenhar sempre por cima
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glColor3f(1.0, 1.0, 1.0)

    # deslocamento leve para o cursor não tampar o texto
    pos_x = mouse_x + 15
    pos_y = mouse_y + 15

    # desenha o quad com o texto
    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 1.0); glVertex2f(pos_x, pos_y)
    glTexCoord2f(1.0, 1.0); glVertex2f(pos_x + text_width, pos_y)
    glTexCoord2f(1.0, 0.0); glVertex2f(pos_x + text_width, pos_y + text_height)
    glTexCoord2f(0.0, 0.0); glVertex2f(pos_x, pos_y + text_height)
    glEnd()

    # restaura o estado original
    glDisable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()

    # deleta a textura temporária para não estourar a memória
    glDeleteTextures(1, [tex_id])


def draw_background(texture_id):
    if texture_id is None:
        return

    # salva as matrizes atuais
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity() 

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # configurações de desenho (desliga o 3D, liga a textura)
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor3f(1.0, 1.0, 1.0)

    # desenha o quad cravado nas bordas absolutas da tela
    glBegin(GL_QUADS)
    
    # mapeamento: UV da Textura (0 a 1) -> Coordenadas da Tela NDC (-1 a 1)
    # como carregamos a imagem invertida no PyGame, o UV (0,0) é embaixo
    
    # canto Inferior Esquerdo
    glTexCoord2f(0.0, 0.0); glVertex2f(-1.0, -1.0) 
    
    # canto Inferior Direito
    glTexCoord2f(1.0, 0.0); glVertex2f( 1.0, -1.0) 
    
    # canto Superior Direito
    glTexCoord2f(1.0, 1.0); glVertex2f( 1.0,  1.0) 
    
    # canto Superior Esquerdo
    glTexCoord2f(0.0, 1.0); glVertex2f(-1.0,  1.0) 
    
    glEnd()

    glDisable(GL_TEXTURE_2D)

    # restaura o controle para o 3D dos planetas
    glEnable(GL_DEPTH_TEST)
    
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()


def draw_fade_overlay(width, height, alpha):
    # so desenha se houver alguma opacidade
    if alpha <= 0.0:
        return

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # desliga a profundidade e desliga texturas para desenhar cor solida
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_TEXTURE_2D)
    
    # cor preta com o canal alpha (transparencia) variavel
    glColor4f(0.0, 0.0, 0.0, alpha)

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

# prepara a cena e as regras de renderização 3D.
def start_opengl(height, width):
    # define a área exata da tela
    glViewport(0, 0, int(width), int(height))

    # define a perspectiva (câmera)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    
    # parâmetros: FOV (45 graus), Aspect Ratio (largura/altura), Near Clipping Plane, Far Clipping Plane
    # tudo que estiver mais perto que 0.1 ou mais longe que 1000 não será renderizado
    gluPerspective(45, (width / height), 0.1, 1000.0)
    
    # retorna para a matriz de visualização de modelos
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    
    # afasta a câmera no eixo Z para podermos ver o centro do espaço
    glTranslatef(0.0, 0.0, -50.0)
    
    # ativa o Z-Buffer (teste de profundidade)
    # fundamental para que modelos 3D não sejam desenhados de dentro para fora
    glEnable(GL_DEPTH_TEST)

    # suporte de canal alpha (transparência)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

def draw_cube(x, y, z, size, height, color=(0.15, 0.2, 0.15)):
    half = size / 2.0
    
    glBegin(GL_QUADS)
    glColor3f(*color) # usa a cor dinâmica
    
    # frente
    glVertex3f(x - half, y,          z + half)
    glVertex3f(x + half, y,          z + half)
    glVertex3f(x + half, y + height, z + half)
    glVertex3f(x - half, y + height, z + half)
    
    # trás
    glVertex3f(x - half, y,          z - half)
    glVertex3f(x - half, y + height, z - half)
    glVertex3f(x + half, y + height, z - half)
    glVertex3f(x + half, y,          z - half)
    
    # esquerda
    glVertex3f(x - half, y,          z - half)
    glVertex3f(x - half, y,          z + half)
    glVertex3f(x - half, y + height, z + half)
    glVertex3f(x - half, y + height, z - half)
    
    # direita
    glVertex3f(x + half, y,          z - half)
    glVertex3f(x + half, y + height, z - half)
    glVertex3f(x + half, y + height, z + half)
    glVertex3f(x + half, y,          z + half)
    glEnd()


def draw_door(x, y, z, size, height, color=(0.4, 0.4, 0.44)):
    half_w = (size / 2.0) * 0.85
    half_d = (size / 2.0) * 0.3
    
    glBegin(GL_QUADS)
    glColor3f(*color)
    
    # frente
    glVertex3f(x - half_w, y,          z + half_d)
    glVertex3f(x + half_w, y,          z + half_d)
    glVertex3f(x + half_w, y + height, z + half_d)
    glVertex3f(x - half_w, y + height, z + half_d)
    
    # trás
    glVertex3f(x - half_w, y,          z - half_d)
    glVertex3f(x - half_w, y + height, z - half_d)
    glVertex3f(x + half_w, y + height, z - half_d)
    glVertex3f(x + half_w, y,          z - half_d)
    
    # esquerda
    glVertex3f(x - half_w, y,          z - half_d)
    glVertex3f(x - half_w, y,          z + half_d)
    glVertex3f(x - half_w, y + height, z + half_d)
    glVertex3f(x - half_w, y + height, z - half_d)
    
    # direita
    glVertex3f(x + half_w, y,          z - half_d)
    glVertex3f(x + half_w, y + height, z - half_d)
    glVertex3f(x + half_w, y + height, z + half_d)
    glVertex3f(x + half_w, y,          z + half_d)
    glEnd()

def draw_floor_tile(x, y, z, size, color=(0.1, 0.1, 0.1)):
    half = size / 2.0
    glBegin(GL_QUADS)
    glColor3f(*color) # usa a cor dinâmica
    glVertex3f(x - half, y, z - half)
    glVertex3f(x - half, y, z + half)
    glVertex3f(x + half, y, z + half)
    glVertex3f(x + half, y, z - half)
    glEnd()

def draw_u_stairs(x, y, z, size, height, direction_char):
    half = size / 2.0
    mid_y = height / 2.0
    
    angles = {'^': 0, '<': 90, 'v': 180, '>': -90}
    angle = angles.get(direction_char, 0)

    glPushMatrix()
    glTranslatef(x, y, z)
    glRotatef(angle, 0, 1, 0)
    
    glColor3f(0.2, 0.25, 0.2)
    glBegin(GL_QUADS)
    
    # patamar
    glVertex3f(-half, mid_y,  0); glVertex3f( half, mid_y,  0)
    glVertex3f( half, mid_y, -half); glVertex3f(-half, mid_y, -half)
    glVertex3f(-half, 0,  0); glVertex3f( half, 0,  0)
    glVertex3f( half, mid_y,  0); glVertex3f(-half, mid_y,  0)
    glVertex3f(-half, 0, -half); glVertex3f(-half, mid_y, -half)
    glVertex3f( half, mid_y, -half); glVertex3f( half, 0, -half)
    glVertex3f(-half, 0, -half); glVertex3f(-half, 0,  0)
    glVertex3f(-half, mid_y,  0); glVertex3f(-half, mid_y, -half)
    glVertex3f( half, 0,  0); glVertex3f( half, 0, -half)
    glVertex3f( half, mid_y, -half); glVertex3f( half, mid_y,  0)
    
    # lance 1
    glVertex3f(0, 0, half); glVertex3f(half, 0, half)
    glVertex3f(half, mid_y, 0); glVertex3f(0, mid_y, 0)
    
    # lance 2
    glVertex3f(-half, mid_y, 0); glVertex3f(0, mid_y, 0)
    glVertex3f(0, height, half); glVertex3f(-half, height, half)
    glVertex3f(-half, 0, half); glVertex3f(0, 0, half)
    glVertex3f(0, height, half); glVertex3f(-half, height, half)
    glEnd()
    
    glBegin(GL_TRIANGLES)
    glVertex3f(half, 0, half); glVertex3f(half, 0, 0); glVertex3f(half, mid_y, 0)
    glVertex3f(0, 0, half); glVertex3f(0, mid_y, 0); glVertex3f(0, 0, 0)
    glEnd()
    
    glBegin(GL_QUADS)
    glVertex3f(-half, 0, half); glVertex3f(-half, 0, 0)
    glVertex3f(-half, mid_y, 0); glVertex3f(-half, height, half)
    glVertex3f(0, 0, half); glVertex3f(0, 0, 0)
    glVertex3f(0, mid_y, 0); glVertex3f(0, height, half)
    glEnd()
    
    glPopMatrix()

def draw_computer(x, y, z, size, wall_height, screen_color=(0.0, 0.0, 0.6)):
    comp_base_w = size * 0.2
    comp_base_d = size * 0.2
    half_w = comp_base_w / 2.0
    half_d = comp_base_d / 2.0
    
    comp_base_h = wall_height * 0.35 
    
    comp_monitor_h = 0.5 
    top_y = comp_monitor_h
    
    # laterais retas
    half_top_w = half_w 
    
    # o topo frontal recua para trás para criar a rampa
    top_front_z = -half_d + (comp_base_d * 0.3) 
    
    color_base = (0.3, 0.3, 0.3)

    glPushMatrix()
    glTranslatef(x, y, z)
    
    # desenhar a base (corpo Principal)
    glColor3fv(color_base)
    glBegin(GL_QUADS)
    # face Frontal
    glVertex3f(-half_w, 0, half_d); glVertex3f(half_w, 0, half_d)
    glVertex3f(half_w, comp_base_h, half_d); glVertex3f(-half_w, comp_base_h, half_d)
    # face Traseira
    glVertex3f(-half_w, 0, -half_d); glVertex3f(-half_w, comp_base_h, -half_d)
    glVertex3f(half_w, comp_base_h, -half_d); glVertex3f(half_w, 0, -half_d)
    # face Esquerda
    glVertex3f(-half_w, 0, -half_d); glVertex3f(-half_w, 0, half_d)
    glVertex3f(-half_w, comp_base_h, half_d); glVertex3f(-half_w, comp_base_h, -half_d)
    # face Direita
    glVertex3f(half_w, 0, -half_d); glVertex3f(half_w, comp_base_h, -half_d)
    glVertex3f(half_w, comp_base_h, half_d); glVertex3f(half_w, 0, half_d)
    # face Superior
    glVertex3f(-half_w, comp_base_h, -half_d); glVertex3f(-half_w, comp_base_h, half_d)
    glVertex3f(half_w, comp_base_h, half_d); glVertex3f(half_w, comp_base_h, -half_d)
    glEnd()

    # desenhar o monitor
    glTranslatef(0, comp_base_h, 0) 
    
    glColor3fv(color_base)
    glBegin(GL_QUADS)
    # costas (reta vertical e alinhada)
    glVertex3f(-half_w, 0, -half_d); glVertex3f(-half_top_w, top_y, -half_d)
    glVertex3f(half_top_w, top_y, -half_d); glVertex3f(half_w, 0, -half_d)
    # esquerda
    glVertex3f(-half_w, 0, -half_d); glVertex3f(-half_w, 0, half_d)
    glVertex3f(-half_top_w, top_y, top_front_z); glVertex3f(-half_top_w, top_y, -half_d)
    # direita
    glVertex3f(half_w, 0, -half_d); glVertex3f(half_top_w, top_y, -half_d)
    glVertex3f(half_top_w, top_y, top_front_z); glVertex3f(half_w, 0, half_d)
    # topo 
    glVertex3f(-half_top_w, top_y, -half_d); glVertex3f(-half_top_w, top_y, top_front_z)
    glVertex3f(half_top_w, top_y, top_front_z); glVertex3f(half_top_w, top_y, -half_d)
    # frente (uma rampa inclinada)
    glVertex3f(-half_w, 0, half_d); glVertex3f(half_w, 0, half_d)
    glVertex3f(half_top_w, top_y, top_front_z); glVertex3f(-half_top_w, top_y, top_front_z)
    glEnd()
    
    # desenhar a tela azul
    margin = 0.1
    screen_bot_y = top_y * margin
    screen_top_y = top_y * (1.0 - margin)
    
    # função matemática para calcular o Z na rampa
    def get_ramp_z(y_val):
        t = y_val / top_y 
        z_val = half_d + t * (top_front_z - half_d)
        return z_val
        
    z_bot = get_ramp_z(screen_bot_y)
    z_top = get_ramp_z(screen_top_y)
    
    x_val = half_w * (1.0 - margin)
    z_offset = 0.01 
    
    glColor3fv(screen_color) 
    glBegin(GL_QUADS)
    glVertex3f(-x_val, screen_bot_y, z_bot + z_offset)
    glVertex3f( x_val, screen_bot_y, z_bot + z_offset)
    glVertex3f( x_val, screen_top_y, z_top + z_offset)
    glVertex3f(-x_val, screen_top_y, z_top + z_offset)
    glEnd()
    
    glPopMatrix()

def draw_creature(x, y, z, yaw_degrees, body_color, glow_color, pulse_time):
    march_offset = math.sin(pulse_time * 0.010) * 6.0
    breath = math.sin(pulse_time * 0.0026)
    breath_scale_x = 1.0 + (breath * 0.14)
    breath_scale_y = 1.0 + (breath * 0.08)
    breath_scale_z = 1.0 + (breath * 0.18)
    breath_lift = breath * 0.18
    chassis_size = BLOCK_SIZE * 0.24
    head_width = chassis_size * 0.92
    head_depth = chassis_size * 0.75
    metal_highlight = tuple(min(1.0, c * 1.22) for c in body_color)
    light_color = tuple(min(1.0, c * 1.18) for c in glow_color)

    glPushMatrix()
    glTranslatef(x, y, z)
    glRotatef(yaw_degrees, 0, 1, 0)
    glTranslatef(0, 1.45 + breath_lift, 0)
    glScalef(breath_scale_x, breath_scale_y, breath_scale_z)
    glTranslatef(0, -1.45, 0)

    # Tronco principal do robo
    draw_cube(0, 0.72, 0, chassis_size, 1.55, color=body_color)
    draw_cube(0, 1.65, -chassis_size * 0.10, chassis_size * 0.90, 0.55, color=metal_highlight)

    # Cabeca retangular
    glPushMatrix()
    glTranslatef(0, 2.22, chassis_size * 0.05)
    draw_cube(0, 0.0, 0, head_width, 0.72, color=metal_highlight)
    draw_cube(0, 0.08, head_depth * 0.22, head_width * 0.72, 0.38, color=metal_highlight)
    glPopMatrix()

    # Antenas / sensores
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(side * head_width * 0.28, 2.92, 0)
        draw_cube(0, 0.0, 0, chassis_size * 0.10, 0.34, color=metal_highlight)
        glTranslatef(0, 0.30, 0)
        draw_cube(0, 0.0, 0, chassis_size * 0.05, 0.14, color=light_color)
        glPopMatrix()

    # Bracos mecanicos segmentados
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(side * (chassis_size * 0.82), 1.92, 0)
        glRotatef(side * (12 + march_offset), 0, 0, 1)
        draw_cube(0, -0.34, 0, chassis_size * 0.20, 0.92, color=body_color)
        glTranslatef(0, -0.78, 0)
        glRotatef(side * -18, 0, 0, 1)
        draw_cube(0, -0.26, 0, chassis_size * 0.16, 0.80, color=metal_highlight)

        # Garra mecanica
        glTranslatef(0, -0.60, chassis_size * 0.06)
        draw_cube(0, -0.06, 0, chassis_size * 0.16, 0.22, color=light_color)
        for claw_side in (-1, 1):
            glPushMatrix()
            glTranslatef(claw_side * chassis_size * 0.10, -0.16, chassis_size * 0.08)
            glRotatef(claw_side * 24, 0, 0, 1)
            draw_cube(0, -0.08, 0, chassis_size * 0.05, 0.30, color=light_color)
            glPopMatrix()
        glPopMatrix()

    # Quadril / junta central
    draw_cube(0, 0.46, 0, chassis_size * 0.62, 0.24, color=metal_highlight)

    # Pernas roboticas
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(side * chassis_size * 0.24, 0.42, 0)
        glRotatef(side * (-6 - march_offset * 0.6), 0, 0, 1)
        draw_cube(0, -0.18, 0, chassis_size * 0.14, 1.00, color=body_color)
        glTranslatef(0, -0.90, 0)
        glRotatef(side * (10 + march_offset * 0.3), 0, 0, 1)
        draw_cube(0, -0.12, 0, chassis_size * 0.12, 0.92, color=metal_highlight)

        # Pe mecanico
        glTranslatef(0, -0.72, chassis_size * 0.10)
        draw_cube(0, -0.05, 0, chassis_size * 0.20, 0.18, color=light_color)
        glPopMatrix()

    eye_glow = 0.82 + ((math.sin(pulse_time * 0.012) + 1.0) * 0.09)
    eye_color = tuple(min(1.0, channel * eye_glow) for channel in glow_color)
    eye_y = 2.48
    eye_z = head_depth * 0.56
    eye_offset = head_width * 0.16
    eye_size = 0.09

    glBegin(GL_QUADS)
    glColor3f(*eye_color)
    for eye_x in (-eye_offset, eye_offset):
        glVertex3f(eye_x - eye_size, eye_y - eye_size, eye_z)
        glVertex3f(eye_x + eye_size, eye_y - eye_size, eye_z)
        glVertex3f(eye_x + eye_size, eye_y + eye_size, eye_z)
        glVertex3f(eye_x - eye_size, eye_y + eye_size, eye_z)
    glEnd()

    # Luz central do peito
    chest_light = tuple(min(1.0, channel * (0.9 + ((math.sin(pulse_time * 0.014) + 1.0) * 0.14))) for channel in glow_color)
    glBegin(GL_QUADS)
    glColor3f(*chest_light)
    glVertex3f(-chassis_size * 0.10, 1.62, chassis_size * 0.52)
    glVertex3f(chassis_size * 0.10, 1.62, chassis_size * 0.52)
    glVertex3f(chassis_size * 0.10, 1.84, chassis_size * 0.52)
    glVertex3f(-chassis_size * 0.10, 1.84, chassis_size * 0.52)
    glEnd()

    glPopMatrix()

def draw_collectible(x, y, z, size, body_color, glow_color, pulse_time):
    pulse_scale = 0.82 + ((math.sin(pulse_time * 0.007) + 1.0) * 0.10)
    bob = math.sin(pulse_time * 0.005) * 0.18
    draw_cube(x, y + 0.5 + bob, z, size * 0.55, 1.25, color=body_color)

    glow = tuple(min(1.0, channel * pulse_scale) for channel in glow_color)
    half = size * 0.26
    top_y = y + 1.95 + bob

    glBegin(GL_QUADS)
    glColor3f(*glow)
    glVertex3f(x - half, top_y, z - half)
    glVertex3f(x - half, top_y, z + half)
    glVertex3f(x + half, top_y, z + half)
    glVertex3f(x + half, top_y, z - half)
    glEnd()


def draw_tech_module(x, y, z, size, body_color, glow_color, pulse_time):
    bob = math.sin(pulse_time * 0.0045) * 0.16
    spin = (pulse_time * 0.045) % 360.0
    pulse = 0.88 + ((math.sin(pulse_time * 0.008) + 1.0) * 0.10)

    base_color = tuple(min(1.0, channel * 0.85) for channel in body_color)
    core_color = tuple(min(1.0, channel * pulse) for channel in glow_color)
    frame_color = tuple(min(1.0, channel * 1.12) for channel in body_color)

    glPushMatrix()
    glTranslatef(x, y + 0.75 + bob, z)
    glRotatef(spin, 0, 1, 0)

    # Base do modulo
    draw_cube(0, 0.0, 0, size * 0.34, 0.55, color=base_color)

    # Corpo central
    draw_cube(0, 0.35, 0, size * 0.22, 0.95, color=frame_color)

    # Aletas laterais para dar cara de equipamento tecnologico
    draw_cube(size * 0.17, 0.42, 0, size * 0.08, 0.72, color=frame_color)
    draw_cube(-size * 0.17, 0.42, 0, size * 0.08, 0.72, color=frame_color)
    draw_cube(0, 0.42, size * 0.17, size * 0.08, 0.72, color=frame_color)
    draw_cube(0, 0.42, -size * 0.17, size * 0.08, 0.72, color=frame_color)

    # Nucleo brilhante
    draw_cube(0, 0.62, 0, size * 0.12, 0.38, color=core_color)

    # Painel superior luminoso
    top_y = 1.38
    panel_half = size * 0.10
    glBegin(GL_QUADS)
    glColor3f(*core_color)
    glVertex3f(-panel_half, top_y, -panel_half)
    glVertex3f(-panel_half, top_y, panel_half)
    glVertex3f(panel_half, top_y, panel_half)
    glVertex3f(panel_half, top_y, -panel_half)
    glEnd()

    # Anel de energia rotacionando em outro eixo
    glRotatef(-spin * 1.7, 1, 0, 0)
    ring_w = size * 0.32
    ring_h = size * 0.03
    ring_y = 0.92
    glBegin(GL_QUADS)
    glColor3f(*core_color)
    glVertex3f(-ring_w, ring_y, -ring_h)
    glVertex3f(ring_w, ring_y, -ring_h)
    glVertex3f(ring_w, ring_y, ring_h)
    glVertex3f(-ring_w, ring_y, ring_h)
    glEnd()

    glPopMatrix()


def draw_alien_crystal(x, y, z, size, body_color, glow_color, pulse_time):
    bob = math.sin(pulse_time * 0.0048) * 0.20
    spin = (pulse_time * 0.040) % 360.0
    pulse = 0.86 + ((math.sin(pulse_time * 0.0085) + 1.0) * 0.12)

    crystal_color = tuple(min(1.0, channel * pulse) for channel in body_color)
    glow_pulse_color = tuple(min(1.0, channel * (pulse + 0.18)) for channel in glow_color)
    shard_color = tuple(min(1.0, channel * 1.08) for channel in body_color)

    glPushMatrix()
    glTranslatef(x, y + 0.75 + bob, z)
    glRotatef(spin, 0, 1, 0)

    # Nucleo do cristal
    draw_cube(0, 0.10, 0, size * 0.22, 1.55, color=crystal_color)

    # Base pequena
    draw_cube(0, -0.15, 0, size * 0.28, 0.22, color=tuple(min(1.0, c * 0.7) for c in body_color))

    # Shards laterais em orbitacao lenta para dar cara alienigena
    for angle in (0, 90, 180, 270):
        glPushMatrix()
        glRotatef(angle + (spin * 0.65), 0, 1, 0)
        glTranslatef(size * 0.20, 0.42, 0)
        glRotatef(35, 0, 0, 1)
        draw_cube(0, 0.0, 0, size * 0.08, 0.95, color=shard_color)
        glPopMatrix()

    # Ponta superior brilhante
    glPushMatrix()
    glTranslatef(0, 1.65, 0)
    glRotatef(45, 0, 1, 0)
    draw_cube(0, 0.0, 0, size * 0.14, 0.45, color=glow_pulse_color)
    glPopMatrix()

    # Halo luminoso
    halo_y = 1.05
    halo_w = size * 0.34
    halo_h = size * 0.035
    glBegin(GL_QUADS)
    glColor3f(*glow_pulse_color)
    glVertex3f(-halo_w, halo_y, -halo_h)
    glVertex3f(halo_w, halo_y, -halo_h)
    glVertex3f(halo_w, halo_y, halo_h)
    glVertex3f(-halo_w, halo_y, halo_h)
    glEnd()

    glPopMatrix()


def draw_exit_module(x, y, z, size, locked_color, unlocked_color, unlocked, pulse_time):
    module_color = unlocked_color if unlocked else locked_color
    draw_cube(x, y, z, size * 0.52, 2.6, color=module_color)

    glow = 0.75 + ((math.sin(pulse_time * 0.007) + 1.0) * 0.14)
    light_color = (0.45, 1.0, 0.55) if unlocked else (0.85, 0.18, 0.18)
    top_color = tuple(min(1.0, channel * glow) for channel in light_color)
    half = (size * 0.34) / 2.0

    glBegin(GL_QUADS)
    glColor3f(*top_color)
    glVertex3f(x - half, y + 2.65, z - half)
    glVertex3f(x - half, y + 2.65, z + half)
    glVertex3f(x + half, y + 2.65, z + half)
    glVertex3f(x + half, y + 2.65, z - half)
    glEnd()
