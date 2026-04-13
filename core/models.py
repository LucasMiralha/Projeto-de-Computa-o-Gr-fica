import json
from dataclasses import dataclass

@dataclass
class PlanetaData:
    name: str
    size: float
    rotation_speed: float
    axis_tilt: float
    color_or_texture: str
    has_rings: bool
    splash_image: str = "" 
    level_name: str = ""
    current_angle: float = 0.0
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    texture_id: int = None
    splash_texture_id: int = None
    is_unlocked: bool = False
    layout: list = None


def load_planets(caminho_arquivo):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
            dados = json.load(arquivo)
            
        lista_planetas = []
        for p in dados['planetas']:
            novo_planeta = PlanetaData(
                name=p['nome'],
                size=p['tamanho'],
                rotation_speed=p['velocidade_rotacao'],
                axis_tilt=p['inclinacao_eixo'],
                color_or_texture=p['cor_ou_textura'],
                has_rings=p['possui_aneis'],
                splash_image=p.get('splash_image', ""),
                level_name=p.get('level_name', ""),
                layout=p.get('layout', [])
            )
            lista_planetas.append(novo_planeta)
            
        return lista_planetas
    
    except Exception as e:
        print(f"Erro ao carregar planetas: {e}")
        return []
