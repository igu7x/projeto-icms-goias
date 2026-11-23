#!/bin/sh
# Atalho para Linux/Mac: instala, monta o banco e abre o painel
pip install -r requirements.txt
python3 etl.py
python3 relatorio.py
streamlit run app.py
