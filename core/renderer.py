import pygame
import math
from OpenGL.GL import *
from OpenGL.GLU import *
from core.graphics_utils import hex_to_rgb
from core.physics_engine import *

# Cache para Display Lists (Otimização para GPU)
_sphere_display_lists = {}
_ring_display_lists = {}
_skysphere_display_list = None
_quadric = None

def _get_quadric():
    global _quadric
    if _quadric is None:
        _quadric = gluNewQuadric()
        gluQuadricTexture(_quadric, GL_TRUE)
    return _quadric

def clear_renderer_caches():
    """Limpa todos os caches de display lists e objetos quadric para evitar erros em reset de contexto."""
    global _sphere_display_lists, _ring_display_lists, _skysphere_display_list, _quadric
    _sphere_display_lists.clear()
    _ring_display_lists.clear()
    _skysphere_display_list = None
    _quadric = None


def draw_textured_floor_tile(x, y, z, size, texture_id=None, bottom_texture_id=None, color=(0.1, 0.1, 0.1), uv_scale=1.0):
    if texture_id is None and bottom_texture_id is None:
        draw_floor_tile(x, y, z, size, color=color)
        return

    half = size / 2.0
    glColor3f(1.0, 1.0, 1.0)
    
    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0); glVertex3f(x - half, y, z - half)
        glTexCoord2f(0.0, uv_scale); glVertex3f(x - half, y, z + half)
        glTexCoord2f(uv_scale, uv_scale); glVertex3f(x + half, y, z + half)
        glTexCoord2f(uv_scale, 0.0); glVertex3f(x + half, y, z - half)
        glEnd()
        glDisable(GL_TEXTURE_2D)
        
    if bottom_texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, bottom_texture_id)
        # Offset minúsculo para baixo para evitar Z-fighting com o chão do andar acima
        y_bottom = y + 3.99
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0); glVertex3f(x - half, y_bottom, z - half)
        glTexCoord2f(0.0, uv_scale); glVertex3f(x - half, y_bottom, z + half)
        glTexCoord2f(uv_scale, uv_scale); glVertex3f(x + half, y_bottom, z + half)
        glTexCoord2f(uv_scale, 0.0); glVertex3f(x + half, y_bottom, z - half)
        glEnd()
        glDisable(GL_TEXTURE_2D)


def draw_textured_cube(x, y, z, size, height, texture_id=None, color=(0.15, 0.2, 0.15), uv_scale=1.0, alpha=1.0):
    if texture_id is None:
        draw_cube(x, y, z, size, height, color=color)
        return

    half = size / 2.0
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor4f(1.0, 1.0, 1.0, alpha)
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
    key = (internal_radius, external_radius)
    
    if key not in _ring_display_lists:
        display_list = glGenLists(1)
        glNewList(display_list, GL_COMPILE)
        quadric = gluNewQuadric()
        gluQuadricTexture(quadric, GL_TRUE)
        gluDisk(quadric, internal_radius, external_radius, 128, 1)
        gluDeleteQuadric(quadric)
        glEndList()
        _ring_display_lists[key] = display_list

    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        # Otimização crucial: descarta pixels transparentes para não escrever no Depth Buffer
        # Isso permite ver o planeta através das partes transparentes do anel
        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GREATER, 0.1)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        
    glCallList(_ring_display_lists[key])
    
    if texture_id is not None:
        glDisable(GL_ALPHA_TEST)
        glDisable(GL_TEXTURE_2D)


def draw_sphere(radius, hex_color, texture_id):
    # Arredonda o raio para cache (evita criar milhares de listas se o raio variar micro-mimetricamente)
    key = round(radius, 3)
    
    if key not in _sphere_display_lists:
        display_list = glGenLists(1)
        glNewList(display_list, GL_COMPILE)
        quadric = gluNewQuadric()
        gluQuadricTexture(quadric, GL_TRUE)
        gluSphere(quadric, 1.0, 32, 32) # Esfera unitária, escalamos depois
        gluDeleteQuadric(quadric)
        glEndList()
        _sphere_display_lists[key] = display_list

    glPushMatrix()
    glScalef(radius, radius, radius)
    
    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor3f(1.0, 1.0, 1.0)
    else:
        glDisable(GL_TEXTURE_2D)
        if hex_color.startswith('#'):
            r, g, b = hex_to_rgb(hex_color)
            glColor3f(r, g, b)

    glCallList(_sphere_display_lists[key])
    glPopMatrix()
    glDisable(GL_TEXTURE_2D)


def draw_parallax_background(texture_id, mouse_pos, screen_width, screen_height, intensity=0.01):
    if texture_id is None:
        return

    # Calcula o deslocamento relativo do mouse (-1 a 1)
    # Ter o centro como referência (0,0)
    rel_x = (mouse_pos[0] / screen_width) * 2 - 1
    rel_y = (mouse_pos[1] / screen_height) * 2 - 1
    
    # Inverte para o fundo se mover na direção OPOSTA
    off_x = -rel_x * intensity
    off_y =  rel_y * intensity # NDC as coordenadas Y são invertidas em relação ao Mouse

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity() 

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor3f(1.0, 1.0, 1.0)

    # Zoom leve para compensar o movimento e não ver bordas pretas
    zoom = 1.0 + intensity

    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 0.0); glVertex2f(-zoom + off_x, -zoom + off_y)
    glTexCoord2f(1.0, 0.0); glVertex2f( zoom + off_x, -zoom + off_y)
    glTexCoord2f(1.0, 1.0); glVertex2f( zoom + off_x,  zoom + off_y)
    glTexCoord2f(0.0, 1.0); glVertex2f(-zoom + off_x,  zoom + off_y)
    glEnd()

    glDisable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST)
    
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()


def draw_tooltip(title, description, mouse_x, mouse_y, screen_width, screen_height, font_title, font_desc, text_color):
    """Desenha uma caixa de informação com título e descrição planetária, suportando múltiplas linhas."""
    
    # Configurações de layout
    max_tooltip_width = 480
    padding = 20
    line_spacing = 5
    wrap_width = max_tooltip_width - (padding * 2)
    
    # 1. Renderiza o título
    title_surface = font_title.render(title, True, text_color)
    t_w, t_h = title_surface.get_size()
    
    # 2. Processa a descrição com quebra de linha (\n) e wrap automático
    paragraphs = description.split('\n')
    wrapped_lines = []
    
    for p in paragraphs:
        if not p.strip():
            wrapped_lines.append("") # Preserva linhas vazias
            continue
            
        words = p.split(' ')
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            w, _ = font_desc.size(test_line)
            if w <= wrap_width:
                current_line.append(word)
            else:
                wrapped_lines.append(' '.join(current_line))
                current_line = [word]
        wrapped_lines.append(' '.join(current_line))
    
    # 3. Renderiza as superfícies de texto da descrição
    desc_color = (210, 210, 210)
    desc_surfaces = [font_desc.render(line, True, desc_color) for line in wrapped_lines]
    
    # 4. Calcula dimensões finais da caixa
    desc_w = 0
    desc_h = 0
    for surf in desc_surfaces:
        sw, sh = surf.get_size()
        desc_w = max(desc_w, sw)
        desc_h += sh + line_spacing
    
    box_width = max(t_w, desc_w, 360) + (padding * 2)
    if box_width > max_tooltip_width: box_width = max_tooltip_width
    
    box_height = t_h + desc_h + (padding * 2) + 8 # gap entre título e desc
    
    # 5. Cria a superfície final do Pygame
    tooltip_surface = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
    
    # Fundo estilizado (Escuro com leve brilho nas bordas)
    pygame.draw.rect(tooltip_surface, (20, 20, 20, 235), (0, 0, box_width, box_height), border_radius=10)
    pygame.draw.rect(tooltip_surface, (130, 130, 130, 255), (0, 0, box_width, box_height), 2, border_radius=10)
    
    # Desenha os textos na superfície
    tooltip_surface.blit(title_surface, (padding, padding))
    
    current_y = padding + t_h + 10
    for surf in desc_surfaces:
        tooltip_surface.blit(surf, (padding, current_y))
        current_y += surf.get_height() + line_spacing
        
    # 6. Converte para textura OpenGL
    dados_imagem = pygame.image.tostring(tooltip_surface, "RGBA", True)
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, box_width, box_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, dados_imagem)

    # 7. Desenho 2D em OpenGL
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
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glColor4f(1.0, 1.0, 1.0, 1.0)

    # Lógica de posicionamento (Confinamento nas bordas da tela)
    pos_x = mouse_x + 25
    pos_y = mouse_y + 25
    
    # Se bater na direita, inverte para a esquerda do cursor
    if pos_x + box_width > screen_width:
        pos_x = mouse_x - box_width - 10
    
    # Se bater em baixo, sobe
    if pos_y + box_height > screen_height:
        pos_y = screen_height - box_height - 10
        
    # Garantia final: nunca sair pelo topo ou esquerda (caso a caixa seja maior que a tela)
    if pos_x < 5: pos_x = 5
    if pos_y < 5: pos_y = 5

    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 1.0); glVertex2f(pos_x, pos_y)
    glTexCoord2f(1.0, 1.0); glVertex2f(pos_x + box_width, pos_y)
    glTexCoord2f(1.0, 0.0); glVertex2f(pos_x + box_width, pos_y + box_height)
    glTexCoord2f(0.0, 0.0); glVertex2f(pos_x, pos_y + box_height)
    glEnd()

    glDisable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()

    glDeleteTextures(1, [tex_id])


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
    
    # Habilita transparência para o fade
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    
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

    # configurações de desenho
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor4f(1.0, 1.0, 1.0, 1.0)

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


# prepara a cena e as regras de renderização 3D.
def start_opengl(height, width):
    # Limpa os caches de desenhos para reconstruir Display Lists no novo contexto
    clear_renderer_caches()

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

def draw_cube(x, y, z, size, height, color=(0.15, 0.2, 0.15), texture_id=None):
    half = size / 2.0
    
    # Fallback para quando o ID da textura  passado na posio da cor (posicional)
    if not isinstance(color, (list, tuple)) and texture_id is None:
        texture_id = color
        color = (1.0, 1.0, 1.0)

    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor3f(1.0, 1.0, 1.0)
    else:
        glDisable(GL_TEXTURE_2D)
        glColor3f(*color)

    glBegin(GL_QUADS)
    
    # frente
    if texture_id is not None: glTexCoord2f(0.0, 1.0)
    glVertex3f(x - half, y,          z + half)
    if texture_id is not None: glTexCoord2f(1.0, 1.0)
    glVertex3f(x + half, y,          z + half)
    if texture_id is not None: glTexCoord2f(1.0, 0.0)
    glVertex3f(x + half, y + height, z + half)
    if texture_id is not None: glTexCoord2f(0.0, 0.0)
    glVertex3f(x - half, y + height, z + half)
    
    # trás
    if texture_id is not None: glTexCoord2f(1.0, 1.0)
    glVertex3f(x - half, y,          z - half)
    if texture_id is not None: glTexCoord2f(1.0, 0.0)
    glVertex3f(x - half, y + height, z - half)
    if texture_id is not None: glTexCoord2f(0.0, 0.0)
    glVertex3f(x + half, y + height, z - half)
    if texture_id is not None: glTexCoord2f(0.0, 1.0)
    glVertex3f(x + half, y,          z - half)
    
    # esquerda
    if texture_id is not None: glTexCoord2f(0.0, 1.0)
    glVertex3f(x - half, y,          z - half)
    if texture_id is not None: glTexCoord2f(1.0, 1.0)
    glVertex3f(x - half, y,          z + half)
    if texture_id is not None: glTexCoord2f(1.0, 0.0)
    glVertex3f(x - half, y + height, z + half)
    if texture_id is not None: glTexCoord2f(0.0, 0.0)
    glVertex3f(x - half, y + height, z - half)
    
    # direita
    if texture_id is not None: glTexCoord2f(1.0, 1.0)
    glVertex3f(x + half, y,          z - half)
    if texture_id is not None: glTexCoord2f(1.0, 0.0)
    glVertex3f(x + half, y + height, z - half)
    if texture_id is not None: glTexCoord2f(0.0, 0.0)
    glVertex3f(x + half, y + height, z + half)
    if texture_id is not None: glTexCoord2f(0.0, 1.0)
    glVertex3f(x + half, y,          z + half)
    glEnd()

    if texture_id is not None:
        glDisable(GL_TEXTURE_2D)


def draw_door(x, y, z, size, height, color=(0.4, 0.4, 0.44)):
    half_w = size / 2.0
    half_d = size / 2.0
    
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

def draw_floor_tile(x, y, z, size, color=(0.1, 0.1, 0.1), texture_id=None):
    half = size / 2.0
    # Fallback para quando o ID da textura  passado na posio da cor (posicional)
    if not isinstance(color, (list, tuple)) and texture_id is None:
        texture_id = color
        color = (1.0, 1.0, 1.0)

    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor3f(1.0, 1.0, 1.0)
    else:
        glDisable(GL_TEXTURE_2D)
        glColor3f(*color)

    glBegin(GL_QUADS)
    if texture_id is not None: glTexCoord2f(0.0, 1.0)
    glVertex3f(x - half, y, z - half)
    if texture_id is not None: glTexCoord2f(0.0, 0.0)
    glVertex3f(x - half, y, z + half)
    if texture_id is not None: glTexCoord2f(1.0, 0.0)
    glVertex3f(x + half, y, z + half)
    if texture_id is not None: glTexCoord2f(1.0, 1.0)
    glVertex3f(x + half, y, z - half)
    glEnd()

    if texture_id is not None:
        glDisable(GL_TEXTURE_2D)

def draw_u_stairs(x, y, z, size, height, direction_char, texture_id=None):
    half = size / 2.0
    mid_y = height / 2.0
    
    angles = {'^': 0, '<': 90, 'v': 180, '>': -90}
    angle = angles.get(direction_char, 0)

    glPushMatrix()
    glTranslatef(x, y, z)
    glRotatef(angle, 0, 1, 0)
    
    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor3f(1.0, 1.0, 1.0)
    else:
        glColor3f(0.2, 0.25, 0.2)
        
    glBegin(GL_QUADS)
    
    def qv(px, py, pz, u, v):
        if texture_id is not None:
            glTexCoord2f(u, v)
        glVertex3f(px, py, pz)
        
    # patamar topo
    qv(-half, mid_y,  0, 0,0); qv( half, mid_y,  0, 1,0)
    qv( half, mid_y, -half, 1,1); qv(-half, mid_y, -half, 0,1)
    # patamar frente
    qv(-half, 0,  0, 0,0); qv( half, 0,  0, 1,0)
    qv( half, mid_y,  0, 1,1); qv(-half, mid_y,  0, 0,1)
    # patamar trás
    qv(-half, 0, -half, 0,0); qv(-half, mid_y, -half, 0,1)
    qv( half, mid_y, -half, 1,1); qv( half, 0, -half, 1,0)
    # patamar lado esquerdo
    qv(-half, 0, -half, 0,0); qv(-half, 0,  0, 1,0)
    qv(-half, mid_y,  0, 1,1); qv(-half, mid_y, -half, 0,1)
    # patamar lado direito
    qv( half, 0,  0, 0,0); qv( half, 0, -half, 1,0)
    qv( half, mid_y, -half, 1,1); qv( half, mid_y,  0, 0,1)
    
    # lance 1 topo
    qv(0, 0, half, 0,0); qv(half, 0, half, 1,0)
    qv(half, mid_y, 0, 1,1); qv(0, mid_y, 0, 0,1)
    
    # lance 2 topo
    qv(-half, mid_y, 0, 0,0); qv(0, mid_y, 0, 1,0)
    qv(0, height, half, 1,1); qv(-half, height, half, 0,1)
    
    # lance 1 interior / baixo
    qv(-half, 0, half, 0,0); qv(0, 0, half, 1,0)
    qv(0, height, half, 1,1); qv(-half, height, half, 0,1)
    
    # Restante de faces transformadas em textured (lance 2 etc)
    qv(-half, 0, half, 0,0); qv(-half, 0, 0, 1,0)
    qv(-half, mid_y, 0, 1,1); qv(-half, height, half, 0,1)
    
    qv(0, 0, half, 0,0); qv(0, 0, 0, 1,0)
    qv(0, mid_y, 0, 1,1); qv(0, height, half, 0,1)
    glEnd()
    
    glBegin(GL_TRIANGLES)
    def tv(px, py, pz, u, v):
        if texture_id is not None:
            glTexCoord2f(u, v)
        glVertex3f(px, py, pz)
        
    tv(half, 0, half, 0,0); tv(half, 0, 0, 1,0); tv(half, mid_y, 0, 0.5,1)
    tv(0, 0, half, 0,0); tv(0, mid_y, 0, 1,1); tv(0, 0, 0, 1,0)
    glEnd()

    if texture_id is not None:
        glDisable(GL_TEXTURE_2D)
    
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

def draw_collectible(x, y, z, size, body_color=None, glow_color=None, pulse_time=None,
                     rotation_angle=0.0, hover_offset=0.0, color=None):
    # Modo Cyber: chamado com keyword args (rotation_angle, hover_offset, color)
    if color is not None:
        half = size / 2.0
        item_y = y + hover_offset

        glPushMatrix()
        glTranslatef(x, item_y, z)
        glRotatef(rotation_angle, 0, 1, 0)

        glDisable(GL_TEXTURE_2D)
        glColor3f(*color)

        # Corpo principal do item (diamante)
        glBegin(GL_TRIANGLES)
        # Pirâmide superior
        glVertex3f(0, half * 1.2, 0)
        glVertex3f(-half, 0, -half)
        glVertex3f(half, 0, -half)

        glVertex3f(0, half * 1.2, 0)
        glVertex3f(half, 0, -half)
        glVertex3f(half, 0, half)

        glVertex3f(0, half * 1.2, 0)
        glVertex3f(half, 0, half)
        glVertex3f(-half, 0, half)

        glVertex3f(0, half * 1.2, 0)
        glVertex3f(-half, 0, half)
        glVertex3f(-half, 0, -half)

        # Pirâmide inferior (invertida)
        glVertex3f(0, -half * 0.6, 0)
        glVertex3f(half, 0, -half)
        glVertex3f(-half, 0, -half)

        glVertex3f(0, -half * 0.6, 0)
        glVertex3f(-half, 0, -half)
        glVertex3f(-half, 0, half)

        glVertex3f(0, -half * 0.6, 0)
        glVertex3f(-half, 0, half)
        glVertex3f(half, 0, half)

        glVertex3f(0, -half * 0.6, 0)
        glVertex3f(half, 0, half)
        glVertex3f(half, 0, -half)
        glEnd()

        glPopMatrix()
        return

    # Modo Arago: chamado com body_color, glow_color, pulse_time
    if body_color is None:
        body_color = (0.18, 0.18, 0.20)
    if glow_color is None:
        glow_color = (0.90, 0.90, 0.60)
    if pulse_time is None:
        pulse_time = 0

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


def draw_stamina_bar(stamina, max_stamina, width, height, exhausted=False):
    """Desenha a barra de stamina no canto inferior esquerdo da tela.
    Todas as dimensões são proporcionais ao tamanho do monitor."""
    bar_width = int(width * 0.18)
    bar_height = int(height * 0.025)
    padding_x = int(width * 0.01)
    padding_y = int(height * 0.02)
    x = padding_x
    y = height - bar_height - padding_y
    fill_ratio = max(0.0, min(1.0, stamina / max_stamina))
    fill_width = int(fill_ratio * (bar_width - 4))

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glDisable(GL_TEXTURE_2D)

    # background
    glColor3f(0.1, 0.1, 0.1)
    glBegin(GL_QUADS)
    glVertex2f(x, y)
    glVertex2f(x + bar_width, y)
    glVertex2f(x + bar_width, y + bar_height)
    glVertex2f(x, y + bar_height)
    glEnd()

    # border
    glColor3f(0.8, 0.8, 0.8)
    glLineWidth(2.0)
    glBegin(GL_LINE_LOOP)
    glVertex2f(x, y)
    glVertex2f(x + bar_width, y)
    glVertex2f(x + bar_width, y + bar_height)
    glVertex2f(x, y + bar_height)
    glEnd()

    # fill
    if exhausted:
        glColor3f(1.0, 0.0, 0.0) # Vermelho se exausto
    else:
        glColor3f(0.0, 0.7, 0.3) # Verde normal
        
    glBegin(GL_QUADS)
    glVertex2f(x + 2, y + 2)
    glVertex2f(x + 2 + fill_width, y + 2)
    glVertex2f(x + 2 + fill_width, y + bar_height - 2)
    glVertex2f(x + 2, y + bar_height - 2)
    glEnd()

    glEnable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()


def draw_ui_text(text, x, y, width, height, font, color=(255, 255, 255), alpha=1.0, align="left"):
    """Função genérica para desenhar texto 2D com texturas OpenGL.
    Suporta alinhamento ('left', 'center', 'right') e transparência."""
    if not text:
        return

    text_surface = font.render(text, True, color)
    text_w, text_h = text_surface.get_size()
    text_data = pygame.image.tostring(text_surface, "RGBA", True)

    pos_x = x
    if align == "center":
        pos_x = x - (text_w / 2)
    elif align == "right":
        pos_x = x - text_w

    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, text_w, text_h, 0, GL_RGBA, GL_UNSIGNED_BYTE, text_data)

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
    
    glColor4f(1.0, 1.0, 1.0, alpha)

    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 1.0); glVertex2f(pos_x, y)
    glTexCoord2f(1.0, 1.0); glVertex2f(pos_x + text_w, y)
    glTexCoord2f(1.0, 0.0); glVertex2f(pos_x + text_w, y + text_h)
    glTexCoord2f(0.0, 0.0); glVertex2f(pos_x, y + text_h)
    glEnd()

    glDisable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()

    glDeleteTextures(1, [tex_id])


def draw_hud_objective(text, width, height, font, color=(240, 240, 240)):
    """Desenha texto de objetivo no canto superior esquerdo da tela."""
    x = int(width * 0.01)
    y = int(height * 0.02)
    draw_ui_text(text, x, y, width, height, font, color, align="left")


def draw_hud_timed_message(text, width, height, font, alpha, color=(240, 240, 240)):
    """Desenha mensagem temporária com transparência na posição 2/3 acima do centro."""
    x = width / 2
    y = int(height * 0.167)
    draw_ui_text(text, x, y, width, height, font, color, alpha=alpha, align="center")


def draw_hud_interaction_prompt(text, width, height, font, color=(240, 240, 240)):
    """Desenha prompt de interação centralizado a 2/3 abaixo do centro da tela."""
    x = width / 2
    y = int(height * 0.833)
    draw_ui_text(text, x, y, width, height, font, color, align="center")

