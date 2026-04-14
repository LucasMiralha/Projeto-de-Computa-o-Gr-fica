import os
import json

def get_save_dir():
    """Retorna o caminho da pasta 'Save/' na raiz do projeto, criando-a se necessário."""
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    save_dir = os.path.join(base_path, 'Save')
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    return save_dir

# ============================================================
#  MAIN SAVE — Progresso global (planetas desbloqueados)
# ============================================================

def _main_save_path():
    return os.path.join(get_save_dir(), 'main_save.json')

def load_main_save():
    """Carrega o progresso global do jogador."""
    path = _main_save_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Erro ao carregar main_save.json: {e}")
    
    # Retorno padrão se o arquivo não existe ou está corrompido
    return {
        "unlocked_planets": [],
        "current_level": None
    }

def save_main_save(unlocked_planets_list, current_level=None):
    """Salva o progresso global: quais planetas estão desbloqueados e qual fase está ativa."""
    data = {
        "unlocked_planets": unlocked_planets_list,
        "current_level": current_level
    }
    _write_json(_main_save_path(), data)

# ============================================================
#  LEVEL SAVE — Estado específico de cada fase
# ============================================================

def _level_save_path(level_name):
    """Gera o caminho do save de uma fase específica: 'Save/level_save_{level_name}.json'"""
    safe_name = level_name.lower().replace(' ', '_')
    return os.path.join(get_save_dir(), f'level_save_{safe_name}.json')

def load_level_save(level_name):
    """
    Carrega o estado salvo de uma fase específica.
    Retorna None se não houver save para essa fase.
    """
    path = _level_save_path(level_name)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Erro ao carregar save da fase '{level_name}': {e}")
    return None

def save_level_save(level_name, data):
    """
    Salva o estado de uma fase específica.
    Cada fase é responsável por montar o dict 'data' com as informações relevantes.
    """
    _write_json(_level_save_path(level_name), data)

def clear_level_save(level_name):
    """Remove o save de uma fase (usado após vitória para evitar reload indesejado)."""
    path = _level_save_path(level_name)
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"Erro ao remover save da fase '{level_name}': {e}")

# ============================================================
#  COMPATIBILIDADE — Funções antigas (redirecionam para as novas)
# ============================================================

def load_game():
    """Compatibilidade: carrega o main_save como se fosse o save_game.json antigo."""
    main = load_main_save()
    # Tenta carregar o level save da fase ativa
    level_data = None
    if main.get("current_level"):
        level_data = load_level_save(main["current_level"])
    return {
        "unlocked_planets": main.get("unlocked_planets", []),
        "level": level_data
    }

def save_global_state(unlocked_planets_list):
    """Compatibilidade: salva apenas os planetas desbloqueados."""
    current = load_main_save()
    save_main_save(unlocked_planets_list, current.get("current_level"))

def save_level_state(cam_x, cam_y, cam_z, player_y, yaw, pitch, planet_name):
    """Compatibilidade: salva estado básico de posição (formato antigo)."""
    save_level_save(planet_name, {
        "planet_name": planet_name,
        "cam_x": cam_x,
        "cam_y": cam_y,
        "cam_z": cam_z,
        "player_y": player_y,
        "yaw": yaw,
        "pitch": pitch
    })
    # Atualiza o main_save para apontar para esta fase
    main = load_main_save()
    save_main_save(main.get("unlocked_planets", []), planet_name)

def clear_level_state():
    """Compatibilidade: limpa o nível ativo do main_save."""
    main = load_main_save()
    if main.get("current_level"):
        clear_level_save(main["current_level"])
    save_main_save(main.get("unlocked_planets", []), None)

# ============================================================
#  Consulta e Limpeza Total
# ============================================================

def has_any_save():
    """Verifica se existe algum save válido (main_save com planetas desbloqueados ou uma fase salva ativa)."""
    main = load_main_save()
    # Tem save se há planetas desbloqueados ou se há uma fase com state salvo
    return len(main.get("unlocked_planets", [])) > 0 or main.get("current_level") is not None

def get_most_advanced_planet(planet_names_ordered):
    """
    Retorna o nome do planeta mais avançado alcançado.
    Percorre a lista em ordem reversa e retorna o primeiro desbloqueado.
    """
    main = load_main_save()
    unlocked = main.get("unlocked_planets", [])
    if not unlocked:
        return None
    # Percorre do mais avançado para o menos
    for name in reversed(planet_names_ordered):
        if name in unlocked:
            return name
    return None

def delete_all_saves():
    """Apaga todos os arquivos .json da pasta Save/."""
    save_dir = get_save_dir()
    try:
        for filename in os.listdir(save_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(save_dir, filename)
                os.remove(filepath)
                print(f"  Save removido: {filename}")
    except Exception as e:
        print(f"Erro ao apagar saves: {e}")

# ============================================================
#  Utilitário interno
# ============================================================

def _write_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar arquivo: {e}")
