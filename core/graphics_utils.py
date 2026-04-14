import pygame
from OpenGL.GL import *
from OpenGL.GLU import *

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def load_texture(image_path):
    try:
        # carrega a imagem
        planet_texture = pygame.image.load(image_path)
        
        # conversão da imagem para uso
        image_data = pygame.image.tostring(planet_texture, "RGBA", True)
        width, height = planet_texture.get_size()

        # gera um id para a textura
        tex_id = glGenTextures(1)
        
        # ativa a textura para configurá-la
        glBindTexture(GL_TEXTURE_2D, tex_id)

        # suaviza a textura quando o planeta estiver muito perto ou muito longe
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        # envia para a placa de vídeo
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, image_data)
        
        return tex_id
    except Exception as e:
        print(f"Erro ao carregar textura '{image_path}': {e}")
        return None
    

def load_background(path, width, height):
    try:
        texture = pygame.image.load(path)
        
        # redimensionamento da imagem
        texture = pygame.transform.smoothscale(texture, (width, height))
        
        image_data = pygame.image.tostring(texture, "RGBA", True)
        
        # as medidas agora são da tela, não da imagem original
        final_width, final_height = texture.get_size()

        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        
        # conserta possíveis desalinhamentos de memória
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        # envia a textura exata e sob medida para a GPU
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, final_width, final_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, image_data)
        
        return tex_id
    
    except Exception as e:
        print(f"Erro ao carregar fundo: {e}")
        return None