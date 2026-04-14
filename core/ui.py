import pygame
from OpenGL.GL import *
from OpenGL.GLU import *

class Button:
    def __init__(self, x, y, width, height, text, font, callback, 
                 base_color=(60, 60, 60, 180), # Adicionado Alpha (180/255)
                 hover_color=(100, 100, 100, 220), 
                 text_color=(255, 255, 255, 255),
                 align="center"): # Novo parâmetro de alinhamento
        
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.callback = callback
        self.align = align.lower()
        self.padding = 10 # Espaço interno para alinhamento left/right
        
        self.base_color = base_color
        self.hover_color = hover_color
        self.text_color = text_color
        
        self.is_hovered = False
        self.text_texture, self.text_w, self.text_h = self._create_text_texture()

    def _create_text_texture(self):
        """Converte o texto do Pygame em uma textura RGBA."""
        # O Pygame renderiza com Alpha se passarmos uma cor com 4 valores
        surface = self.font.render(self.text, True, self.text_color)
        text_data = pygame.image.tostring(surface, "RGBA", True)
        width, height = surface.get_size()

        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, text_data)
        
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        
        return tex_id, width, height

    def check_hover(self, mouse_pos):
        self.is_hovered = self.rect.collidepoint(mouse_pos)
        return self.is_hovered

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_hovered:
                self.callback()

    def _calculate_text_x(self):
        """Calcula a posição X do texto baseado no alinhamento."""
        if self.align == "left":
            return self.rect.x + self.padding
        elif self.align == "right":
            return self.rect.x + self.rect.width - self.text_w - self.padding
        else: # default: center
            return self.rect.x + (self.rect.width - self.text_w) / 2

    def draw(self):
        # Escolhe a cor baseada no hover
        c = self.hover_color if self.is_hovered else self.base_color
        
        # 1. Desenha o Retângulo com transparência (glColor4f)
        glDisable(GL_TEXTURE_2D)
        # Normalizamos para 0.0 - 1.0 dividindo por 255
        glColor4f(c[0]/255, c[1]/255, c[2]/255, c[3]/255)
        
        glBegin(GL_QUADS)
        glVertex2f(self.rect.x, self.rect.y)
        glVertex2f(self.rect.x + self.rect.width, self.rect.y)
        glVertex2f(self.rect.x + self.rect.width, self.rect.y + self.rect.height)
        glVertex2f(self.rect.x, self.rect.y + self.rect.height)
        glEnd()

        # 2. Desenha o Texto
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.text_texture)
        glColor4f(1.0, 1.0, 1.0, 1.0) # Branco sólido para o texto
        
        tx = self._calculate_text_x()
        ty = self.rect.y + (self.rect.height - self.text_h) / 2

        glBegin(GL_QUADS)
        glTexCoord2f(0, 1); glVertex2f(tx, ty)
        glTexCoord2f(1, 1); glVertex2f(tx + self.text_w, ty)
        glTexCoord2f(1, 0); glVertex2f(tx + self.text_w, ty + self.text_h)
        glTexCoord2f(0, 0); glVertex2f(tx, ty + self.text_h)
        glEnd()


class Title:
    def __init__(self, x, y, width, height, text, font, 
                 bg_color=(0, 0, 0, 0), # Default transparente
                 text_color=(95, 198, 139, 255), 
                 align="center"):
        
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.align = align.lower()
        self.padding = 10
        
        self.bg_color = bg_color
        self.text_color = text_color
        
        # Gerar a textura do título
        self.text_texture, self.text_w, self.text_h = self._create_text_texture()

    def _create_text_texture(self):
        """Converte o texto do título em uma textura RGBA."""
        surface = self.font.render(self.text, True, self.text_color)
        text_data = pygame.image.tostring(surface, "RGBA", True)
        width, height = surface.get_size()

        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, text_data)
        
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        
        return tex_id, width, height

    def _calculate_text_x(self):
        """Calcula a posição X do texto baseado no alinhamento."""
        if self.align == "left":
            return self.rect.x + self.padding
        elif self.align == "right":
            return self.rect.x + self.rect.width - self.text_w - self.padding
        else: # center
            return self.rect.x + (self.rect.width - self.text_w) / 2

    def draw(self):
        """Renderiza o título e seu fundo."""
        # 1. Desenha o Retângulo de fundo (caso queira uma faixa atrás do título)
        glDisable(GL_TEXTURE_2D)
        glColor4f(self.bg_color[0] / 255, self.bg_color[1] / 255, 
                  self.bg_color[2] / 255, self.bg_color[3] / 255)
        
        glBegin(GL_QUADS)
        glVertex2f(self.rect.x, self.rect.y)
        glVertex2f(self.rect.x + self.rect.width, self.rect.y)
        glVertex2f(self.rect.x + self.rect.width, self.rect.y + self.rect.height)
        glVertex2f(self.rect.x, self.rect.y + self.rect.height)
        glEnd()

        # 2. Desenha o Texto do Título
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.text_texture)
        glColor4f(1.0, 1.0, 1.0, 1.0) 
        
        tx = self._calculate_text_x()
        ty = self.rect.y + (self.rect.height - self.text_h) / 2

        glBegin(GL_QUADS)
        glTexCoord2f(0, 1); glVertex2f(tx, ty)
        glTexCoord2f(1, 1); glVertex2f(tx + self.text_w, ty)
        glTexCoord2f(1, 0); glVertex2f(tx + self.text_w, ty + self.text_h)
        glTexCoord2f(0, 0); glVertex2f(tx, ty + self.text_h)
        glEnd()

    def set_text(self, new_text):
        """Atualiza o texto e recria a textura OpenGL."""
        glDeleteTextures(1, [self.text_texture])
        self.text = new_text
        self.text_texture, self.text_w, self.text_h = self._create_text_texture()