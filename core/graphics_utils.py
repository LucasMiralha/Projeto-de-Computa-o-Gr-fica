import os
import sys
import pygame
from OpenGL.GL import *
from OpenGL.GLU import *

from core.models import load_planets

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
    

def load_game_resources(script_path:str, json_path: str, screen_width:int, screen_height:int):

    print(f"\nBuscando arquivo json em:\n-> {json_path}")

    # carrega planetas no diretório encontrado
    star_system = load_planets(json_path)

    # se a lista estiver vazia, encerra o jogo
    if not star_system:
        print("\nA lista de planetas está vazia ou o arquivo não foi lido.")
        pygame.quit()
        sys.exit()

    # se o arquivo foi carregado, imprime os planetas lidos
    print("\nPlanetas carregados:")
    for planeta in star_system:
        print(f" -> {planeta.name} (Tamanho: {planeta.size} | Cor: {planeta.color_or_texture})")

    pasta_assets = os.path.join(script_path, 'Assets') # pega a pasta de assets

    pasta_texturas = os.path.join(pasta_assets, 'Planet Textures') # pega a pasta de texturas
    
    pasta_backgrounds = os.path.join(pasta_assets, 'Backgrounds') # pega a pasta de backgrounds

    pasta_splash = os.path.join(pasta_assets, 'Splash') # pega a pasta de splash arts

    pasta_fonts = os.path.join(pasta_assets, 'Fonts')
    
    pasta_sounds = os.path.join(pasta_assets, 'Sounds')

    font_path = os.path.join(pasta_fonts, 'united-sans-reg-bold.otf')

    music_path = os.path.join(pasta_sounds, 'Deep Space Travel Ambience 3 (Menu).mp3')

    for planet in star_system:
        # verifica se o campo parece ser um arquivo de imagem
        if planet.color_or_texture.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(pasta_texturas, planet.color_or_texture)
            planet.texture_id = load_texture(image_path)
            status = f"Textura carregada (ID {planet.texture_id})" if planet.texture_id else "Falha na textura"
            print(f" -> {planet.name}: {status}")
        else:
            print(f" -> {planet.name}: Usando cor sólida ({planet.color_or_texture})")

        # carrega as splash arts dos planetas
        if planet.splash_image:
            splash_path = os.path.join(pasta_splash, planet.splash_image)
            planet.splash_texture_id = load_background(splash_path, screen_width, screen_height)

    # caminho da textura do anel
    ring_image_path = os.path.join(pasta_texturas, 'anel.png')

    ring_texture_id = load_texture(ring_image_path)

    if ring_texture_id:
        print(" -> Textura dos aneis planetários carregada com sucesso!")
    else:
        print(" -> Textura 'anel.png' não encontrada")
    
    background_image_path = os.path.join(pasta_backgrounds, 'fundo_espacial.png')

    background_texture_id = load_background(background_image_path, screen_width, screen_height)

    if background_texture_id:
        print(" -> Textura de fundo carregada com sucesso!")
    else:
        print(" -> Textura 'fundo_espacial.png' não encontrada")
    
    return star_system, background_texture_id, ring_texture_id, font_path, music_path