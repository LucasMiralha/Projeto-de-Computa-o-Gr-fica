import json
import random
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
    current_angle: float = 0.0
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    texture_id: int = None
    splash_texture_id: int = None
    is_unlocked: bool = False
    layout: list = None


def generate_random_vendas_layout(width=30, height=30):
    # Gera um mapa 30x30 com bordas de paredes 'P' e interior aleatorio.
    grid = [
        ['P' if x == 0 or x == width - 1 or y == 0 or y == height - 1 else '.'
         for x in range(width)]
        for y in range(height)
    ]

    spawn_x, spawn_y = 1, 1
    grid[spawn_y][spawn_x] = '@'

    interior_cells = [
        (x, y)
        for y in range(1, height - 1)
        for x in range(1, width - 1)
        if (x, y) != (spawn_x, spawn_y)
    ]

    random.shuffle(interior_cells)
    wall_count = random.randint(180, 260)

    for x, y in interior_cells:
        if wall_count <= 0:
            break

        if abs(x - spawn_x) + abs(y - spawn_y) <= 1:
            continue

        grid[y][x] = 'P'
        wall_count -= 1

    element_cells = [
        (x, y)
        for y in range(1, height - 1)
        for x in range(1, width - 1)
        if grid[y][x] == '.'
    ]
    random.shuffle(element_cells)

    for symbol, amount in [('M', random.randint(6, 12)), ('V', random.randint(20, 40))]:
        for _ in range(amount):
            if not element_cells:
                break
            x, y = element_cells.pop()
            grid[y][x] = symbol

    return [[''.join(row) for row in grid]]


def load_planets(caminho_arquivo):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
            dados = json.load(arquivo)
            
        lista_planetas = []
        for p in dados['planetas']:
            layout = p.get('layout', [])

            if p.get('gerar_layout_aleatorio', False) and not layout:
                layout = generate_random_vendas_layout()

            novo_planeta = PlanetaData(
                name=p['nome'],
                size=p['tamanho'],
                rotation_speed=p['velocidade_rotacao'],
                axis_tilt=p['inclinacao_eixo'],
                color_or_texture=p['cor_ou_textura'],
                has_rings=p['possui_aneis'],
                splash_image=p.get('splash_image', ""),
                layout=layout
            )
            lista_planetas.append(novo_planeta)
            
        return lista_planetas
    
    except Exception as e:
        print(f"Erro ao carregar planetas: {e}")
        return []
