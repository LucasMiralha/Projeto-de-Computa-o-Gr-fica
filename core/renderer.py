import pygame
from OpenGL.GL import *
from OpenGL.GLU import *
from core.graphics_utils import hex_to_rgb

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

def draw_cube(x, y, z, size, height, texture_id=None, draw_top=True, color=None):
    half = size / 2.0

    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor3f(1.0, 1.0, 1.0)
    else:
        glDisable(GL_TEXTURE_2D)
        if color is not None:
            glColor3f(*color)
        else:
            glColor3f(0.15, 0.2, 0.15)

    glBegin(GL_QUADS)
    # frente
    glTexCoord2f(0.0, 0.0); glVertex3f(x - half, y,          z + half)
    glTexCoord2f(1.0, 0.0); glVertex3f(x + half, y,          z + half)
    glTexCoord2f(1.0, 1.0); glVertex3f(x + half, y + height, z + half)
    glTexCoord2f(0.0, 1.0); glVertex3f(x - half, y + height, z + half)

    # trás
    glTexCoord2f(0.0, 0.0); glVertex3f(x - half, y,          z - half)
    glTexCoord2f(0.0, 1.0); glVertex3f(x - half, y + height, z - half)
    glTexCoord2f(1.0, 1.0); glVertex3f(x + half, y + height, z - half)
    glTexCoord2f(1.0, 0.0); glVertex3f(x + half, y,          z - half)

    # esquerda
    glTexCoord2f(0.0, 0.0); glVertex3f(x - half, y,          z - half)
    glTexCoord2f(1.0, 0.0); glVertex3f(x - half, y,          z + half)
    glTexCoord2f(1.0, 1.0); glVertex3f(x - half, y + height, z + half)
    glTexCoord2f(0.0, 1.0); glVertex3f(x - half, y + height, z - half)

    # direita
    glTexCoord2f(0.0, 0.0); glVertex3f(x + half, y,          z - half)
    glTexCoord2f(1.0, 0.0); glVertex3f(x + half, y + height, z - half)
    glTexCoord2f(1.0, 1.0); glVertex3f(x + half, y + height, z + half)
    glTexCoord2f(0.0, 1.0); glVertex3f(x + half, y,          z + half)

    if draw_top:
        # topo
        glTexCoord2f(0.0, 0.0); glVertex3f(x - half, y + height, z - half)
        glTexCoord2f(1.0, 0.0); glVertex3f(x + half, y + height, z - half)
        glTexCoord2f(1.0, 1.0); glVertex3f(x + half, y + height, z + half)
        glTexCoord2f(0.0, 1.0); glVertex3f(x - half, y + height, z + half)

    # inferior
    glTexCoord2f(0.0, 0.0); glVertex3f(x - half, y,          z - half)
    glTexCoord2f(1.0, 0.0); glVertex3f(x + half, y,          z - half)
    glTexCoord2f(1.0, 1.0); glVertex3f(x + half, y,          z + half)
    glTexCoord2f(0.0, 1.0); glVertex3f(x - half, y,          z + half)
    glEnd()

    if texture_id is not None:
        glDisable(GL_TEXTURE_2D)


def draw_floor_tile(x, y, z, size, texture_id=None):
    half = size / 2.0

    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor3f(1.0, 1.0, 1.0)
    else:
        glDisable(GL_TEXTURE_2D)
        glColor3f(0.1, 0.1, 0.1)

    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 0.0); glVertex3f(x - half, y, z - half)
    glTexCoord2f(0.0, 1.0); glVertex3f(x - half, y, z + half)
    glTexCoord2f(1.0, 1.0); glVertex3f(x + half, y, z + half)
    glTexCoord2f(1.0, 0.0); glVertex3f(x + half, y, z - half)
    glEnd()

    if texture_id is not None:
        glDisable(GL_TEXTURE_2D)


def draw_u_stairs(x, y, z, size, height, direction_char, texture_id=None):
    half = size / 2.0
    mid_y = height / 2.0
    
    angles = {'^': 0, '<': 90, 'v': 180, '>': -90}
    angle = angles.get(direction_char, 0)

    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor3f(1.0, 1.0, 1.0)
    else:
        glDisable(GL_TEXTURE_2D)
        glColor3f(0.2, 0.25, 0.2)

    glPushMatrix()
    glTranslatef(x, y, z)
    glRotatef(angle, 0, 1, 0)
    
    glBegin(GL_QUADS)
    
    # patamar
    glTexCoord2f(0.0, 0.0); glVertex3f(-half, mid_y,  0)
    glTexCoord2f(1.0, 0.0); glVertex3f( half, mid_y,  0)
    glTexCoord2f(1.0, 1.0); glVertex3f( half, mid_y, -half)
    glTexCoord2f(0.0, 1.0); glVertex3f(-half, mid_y, -half)

    glTexCoord2f(0.0, 0.0); glVertex3f(-half, 0,  0)
    glTexCoord2f(1.0, 0.0); glVertex3f( half, 0,  0)
    glTexCoord2f(1.0, 1.0); glVertex3f( half, mid_y,  0)
    glTexCoord2f(0.0, 1.0); glVertex3f(-half, mid_y,  0)

    glTexCoord2f(0.0, 0.0); glVertex3f(-half, 0, -half)
    glTexCoord2f(1.0, 0.0); glVertex3f(-half, mid_y, -half)
    glTexCoord2f(1.0, 1.0); glVertex3f( half, mid_y, -half)
    glTexCoord2f(0.0, 1.0); glVertex3f( half, 0, -half)

    glTexCoord2f(0.0, 0.0); glVertex3f(-half, 0, -half)
    glTexCoord2f(1.0, 0.0); glVertex3f(-half, 0,  0)
    glTexCoord2f(1.0, 1.0); glVertex3f(-half, mid_y,  0)
    glTexCoord2f(0.0, 1.0); glVertex3f(-half, mid_y, -half)

    glTexCoord2f(0.0, 0.0); glVertex3f( half, 0,  0)
    glTexCoord2f(1.0, 0.0); glVertex3f( half, 0, -half)
    glTexCoord2f(1.0, 1.0); glVertex3f( half, mid_y, -half)
    glTexCoord2f(0.0, 1.0); glVertex3f( half, mid_y,  0)
    
    # lance 1
    glTexCoord2f(0.0, 0.0); glVertex3f(0, 0, half)
    glTexCoord2f(1.0, 0.0); glVertex3f(half, 0, half)
    glTexCoord2f(1.0, 1.0); glVertex3f(half, mid_y, 0)
    glTexCoord2f(0.0, 1.0); glVertex3f(0, mid_y, 0)

    # lance 2
    glTexCoord2f(0.0, 0.0); glVertex3f(-half, mid_y, 0)
    glTexCoord2f(1.0, 0.0); glVertex3f(0, mid_y, 0)
    glTexCoord2f(1.0, 1.0); glVertex3f(0, height, half)
    glTexCoord2f(0.0, 1.0); glVertex3f(-half, height, half)

    glTexCoord2f(0.0, 0.0); glVertex3f(-half, 0, half)
    glTexCoord2f(1.0, 0.0); glVertex3f(0, 0, half)
    glTexCoord2f(1.0, 1.0); glVertex3f(0, height, half)
    glTexCoord2f(0.0, 1.0); glVertex3f(-half, height, half)
    glEnd()
    
    glBegin(GL_TRIANGLES)
    glTexCoord2f(0.0, 0.0); glVertex3f(half, 0, half)
    glTexCoord2f(1.0, 0.0); glVertex3f(half, 0, 0)
    glTexCoord2f(0.5, 1.0); glVertex3f(half, mid_y, 0)

    glTexCoord2f(0.0, 0.0); glVertex3f(0, 0, half)
    glTexCoord2f(1.0, 0.0); glVertex3f(0, mid_y, 0)
    glTexCoord2f(0.5, 1.0); glVertex3f(0, 0, 0)
    glEnd()
    
    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 0.0); glVertex3f(-half, 0, half)
    glTexCoord2f(1.0, 0.0); glVertex3f(-half, 0, 0)
    glTexCoord2f(1.0, 1.0); glVertex3f(-half, mid_y, 0)
    glTexCoord2f(0.0, 1.0); glVertex3f(-half, height, half)

    glTexCoord2f(0.0, 0.0); glVertex3f(0, 0, half)
    glTexCoord2f(1.0, 0.0); glVertex3f(0, 0, 0)
    glTexCoord2f(1.0, 1.0); glVertex3f(0, mid_y, 0)
    glTexCoord2f(0.0, 1.0); glVertex3f(0, height, half)
    glEnd()
    
    glPopMatrix()

    if texture_id is not None:
        glDisable(GL_TEXTURE_2D)

def draw_computer(x, y, z, size, wall_height):
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
    color_screen = (0.0, 0.0, 0.6)

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
    
    glColor3fv(color_screen)
    glBegin(GL_QUADS)
    glVertex3f(-x_val, screen_bot_y, z_bot + z_offset)
    glVertex3f( x_val, screen_bot_y, z_bot + z_offset)
    glVertex3f( x_val, screen_top_y, z_top + z_offset)
    glVertex3f(-x_val, screen_top_y, z_top + z_offset)
    glEnd()
    
    glPopMatrix()


def draw_collectible_triangle(x, y, z, size, rotation_angle, hover_offset, color=(1.0, 0.92, 0.35)):
    half = size / 2.0

    glDisable(GL_TEXTURE_2D)
    glPushMatrix()
    glTranslatef(x, y + hover_offset, z)
    glRotatef(rotation_angle, 0, 1, 0)
    glColor3f(*color)

    # topo
    glBegin(GL_TRIANGLES)
    glVertex3f(0.0, size, 0.0)
    glVertex3f(-half, 0.0, half)
    glVertex3f(half, 0.0, half)

    glVertex3f(0.0, size, 0.0)
    glVertex3f(half, 0.0, half)
    glVertex3f(half, 0.0, -half)

    glVertex3f(0.0, size, 0.0)
    glVertex3f(half, 0.0, -half)
    glVertex3f(-half, 0.0, -half)

    glVertex3f(0.0, size, 0.0)
    glVertex3f(-half, 0.0, -half)
    glVertex3f(-half, 0.0, half)
    glEnd()

    # base
    glBegin(GL_QUADS)
    glVertex3f(-half, 0.0, half)
    glVertex3f(half, 0.0, half)
    glVertex3f(half, 0.0, -half)
    glVertex3f(-half, 0.0, -half)
    glEnd()

    glPopMatrix()
