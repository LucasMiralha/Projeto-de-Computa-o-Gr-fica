import math

# constantes físicas do mundo
BLOCK_SIZE = 4.0  # tamanho de cada bloco (parede/corredor)
WALL_HEIGHT = 4.0 # altura das paredes

def is_wall(x, y, z, level_map):
    col = int(round(x / BLOCK_SIZE))
    row = int(round(z / BLOCK_SIZE))
    
    pe_y = y - 2.0
    andar = int(math.floor((pe_y + 0.5) / WALL_HEIGHT))
    
    if andar < 0 or andar >= len(level_map) or row < 0 or row >= len(level_map[andar]) or col < 0 or col >= len(level_map[andar][0]):
        return True
        
    char = level_map[andar][row][col]
    
    if char in ['P', 'V', ' ', 'N', 'S', 'L', 'O']:
        return True
        
    if char in ['<', '>', '^', 'v']:
        block_x = col * BLOCK_SIZE
        block_z = row * BLOCK_SIZE
        h = get_stair_height(x, z, block_x, block_z, BLOCK_SIZE, WALL_HEIGHT, char)
        altura_absoluta = (andar * WALL_HEIGHT) + h
        
        # bloqueia se o desnível do degrau for maior que 1.5 (impede entrar pelas laterais)
        if altura_absoluta - pe_y > 1.5:
            return True

    if char == 'M':
        block_x = col * BLOCK_SIZE
        block_z = row * BLOCK_SIZE
        
        # usa as mesmas proporções geométricas do renderer (20% do bloco)
        half_w = (BLOCK_SIZE * 0.2) / 2.0
        half_d = (BLOCK_SIZE * 0.2) / 2.0
        
        # verifica se o X e o Z do jogador estão dentro do quadrado do computador
        if (block_x - half_w) <= x <= (block_x + half_w) and (block_z - half_d) <= z <= (block_z + half_d):
            # verifica se o jogador não está passando por cima do computador
            altura_comp = (andar * WALL_HEIGHT) + (WALL_HEIGHT * 0.35) + 0.5
            if pe_y < altura_comp:
                return True
    
    return False

def has_ramp_below(y_index, z_index, x_index, level_map):
    if y_index == 0:
        return False
    
    andar_abaixo = level_map[y_index - 1]
    
    if z_index < len(andar_abaixo):
        linha_abaixo = andar_abaixo[z_index]
        if x_index < len(linha_abaixo):
            # reconhece as escadas direcionais
            if linha_abaixo[x_index] in ['<', '>', '^', 'v']:
                return True
    
    return False

def get_target_y(x, y, z, level_map):
    col = int(round(x / BLOCK_SIZE))
    row = int(round(z / BLOCK_SIZE))
    
    # calcula a altura dos pés e aplica tolerância para o andar
    pe_y = y - 2.0
    andar = int(math.floor((pe_y + 0.5) / WALL_HEIGHT)) 
    
    if andar < 0: andar = 0
    if andar >= len(level_map): andar = len(level_map) - 1
    
    if row < 0 or row >= len(level_map[andar]) or col < 0 or col >= len(level_map[andar][0]):
        return (andar * WALL_HEIGHT) + 2.0
    
    char = level_map[andar][row][col]
    base_y = andar * WALL_HEIGHT
    
    # se pisou na escada do andar atual
    if char in ['<', '>', '^', 'v']:
        block_x = col * BLOCK_SIZE
        block_z = row * BLOCK_SIZE
        h = get_stair_height(x, z, block_x, block_z, BLOCK_SIZE, WALL_HEIGHT, char)
        return base_y + h + 2.0
    
    # se for dar o passo para descer (lê o andar de baixo)
    if andar > 0 and row < len(level_map[andar-1]) and col < len(level_map[andar-1][row]):
        char_abaixo = level_map[andar-1][row][col]
        if char_abaixo in ['<', '>', '^', 'v']:
            block_x = col * BLOCK_SIZE
            block_z = row * BLOCK_SIZE
            h = get_stair_height(x, z, block_x, block_z, BLOCK_SIZE, WALL_HEIGHT, char_abaixo)
            return ((andar - 1) * WALL_HEIGHT) + h + 2.0
    
    # chão comum
    return base_y + 2.0

def get_stair_height(x, z, block_x, block_z, block_size, wall_height, direction_char):
    half = block_size / 2.0
    mid_y = wall_height / 2.0
    
    # coordenadas locais em relação ao centro do bloco
    lx = x - block_x
    lz = z - block_z
    
    # rotaciona inversamente as coordenadas baseadas na direção da escada
    if direction_char == '<':
        lx, lz = -lz, lx

    elif direction_char == 'v':
        lx, lz = -lx, -lz

    elif direction_char == '>':
        lx, lz = lz, -lx
    
    # avalia a altura baseada na escada
    if lz <= 0:
        return mid_y # patamar
    
    else:
        if lx > 0:
            # lance 1 (Sobe de 0 até o meio)
            progress = (half - lz) / half
            return progress * mid_y
        
        else:
            # lance 2 (Sobe do meio até o topo)
            progress = lz / half
            return mid_y + (progress * mid_y)
