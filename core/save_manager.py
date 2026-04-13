import os
import json

def get_save_path():
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    save_dir = os.path.join(base_path, 'save')
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    return os.path.join(save_dir, 'save_game.json')

def load_game():
    path = get_save_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Erro ao carregar save_game.json: {e}")
            
    # Retorno padrão se arquivo não existe ou corrompido
    return {
        "unlocked_planets": [],
        "level": None
    }

def save_global_state(unlocked_planets_list):
    data = load_game()
    data["unlocked_planets"] = unlocked_planets_list
    _write_save(data)

def save_level_state(cam_x, cam_y, cam_z, player_y, yaw, pitch, planet_name):
    data = load_game()
    data["level"] = {
        "cam_x": cam_x,
        "cam_y": cam_y,
        "cam_z": cam_z,
        "player_y": player_y,
        "yaw": yaw,
        "pitch": pitch,
        "planet_name": planet_name
    }
    _write_save(data)

def clear_level_state():
    """ Usado quando a fase é completada com sucesso, evitando recarregar caso queira voltar do 0 na próx. """
    data = load_game()
    data["level"] = None
    _write_save(data)

def _write_save(data):
    path = get_save_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Erro ao salvar jogo: {e}")
