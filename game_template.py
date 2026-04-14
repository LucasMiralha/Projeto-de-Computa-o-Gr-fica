import importlib
import sys
import os

# agora atua como ponte para todas as fases, motores de gameplay agora estão em "levels/fase.py"
def start(planet, saved_state=None):
    
    level_name = planet.level_name

    module_path = f"levels.{level_name}"

    try:
        # importa o módulo dinamicamente
        level_module = importlib.import_module(module_path)
        
        # executa a função principal do nível
        # cada nível deve ter uma função 'run' que contém o loop
        return level_module.start(planet, saved_state=saved_state)
        
    except ImportError as e:
        print(f"\nScript de fase não encontrado: {module_path}")
        print(f"Certifique-se de que o arquivo levels/{level_name} existe.")
        return "MENU"