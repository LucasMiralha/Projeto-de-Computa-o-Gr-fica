# Lethal Ceti

## Sobre o Projeto
Este repositório contém o código do jogo Lethal Ceti. O foco do projeto é a aplicação prática de conceitos de computação gráfica e o desenvolvimento de jogos utilizando a linguagem Python e suas bibliotecas Pygame e PyOpengl. O sistema implementa um motor próprio que inclui módulos dedicados para inteligência artificial, física, renderização e interface de usuário.

## Estrutura do Repositório
* Assets: Pasta com os recursos visuais e sonoros da aplicação, englobando texturas de planetas, fundos espaciais, artes e efeitos de áudio.
* core: Diretório que abriga a base do motor do jogo. Inclui os utilitários gráficos, regras de física, inteligência artificial, renderizador e o gerenciamento de progresso.
* levels: Contém os scripts que definem a lógica e a construção das fases individuais do jogo.
* Lethal Ceti.py: O arquivo principal responsável por iniciar a aplicação.
* planetas.json: Arquivo estruturado com as configurações e os dados dos planetas disponíveis.
* Save: Pasta destinada ao armazenamento local do progresso do jogador.

## Requisitos Prévios
Para rodar o projeto, é necessário ter a linguagem Python instalada e configurada em sua máquina. O jogo irá verificar automaticamente se as dependências necessárias estão instaladas e tentará instalá-las caso não estejam. Caso o jogo não consiga instalar as dependências automaticamente, instale-as manualmente utilizando o comando: "pip install pygame PyOpenGL numpy" ou "pip install -r requirements.txt"

## Instruções de Execução
Abra o terminal em seu computador e navegue até a pasta raiz do repositório. Inicie o jogo executando o script principal através do comando abaixo:

```
python "Lethal Ceti.py"
```

Ou simplesmente dê dois cliques no arquivo "Lethal Ceti.py" para executá-lo e iniciar o jogo.

## Controles

* W: mover para frente
* S: mover para trás
* A: mover para a esquerda
* D: mover para a direita
* E: interagir
* ESC: menu de pausa
