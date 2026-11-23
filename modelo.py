"""
Modelo estatístico: correlação de Pearson + regressão linear simples.

    X (variável explicativa)  = frota ativa de veículos do município
    Y (variável resposta)     = ICMS repassado ao município no ano (R$)

    Equação da reta:  Ŷ = b + aX
        a = inclinação  = Σ(x - x̄)(y - ȳ) / Σ(x - x̄)²
        b = intercepto  = ȳ - a·x̄

Os coeficientes são calculados "na mão" (numpy) e conferidos com o statsmodels.
"""
import sqlite3

import numpy as np
import pandas as pd
import statsmodels.api as sm

import config


def carregar_dados(caminho=config.CAMINHO_BANCO):
    """Consulta a view do banco (nada de CSV aqui)."""
    with sqlite3.connect(caminho) as con:
        return pd.read_sql_query(
            "SELECT municipio, frota_total, icms_total FROM vw_analise ORDER BY icms_total DESC", con
        )


def classificar_r(r):
    forca = abs(r)
    if forca >= 0.9:
        nivel = "muito forte"
    elif forca >= 0.7:
        nivel = "forte"
    elif forca >= 0.5:
        nivel = "moderada"
    elif forca >= 0.3:
        nivel = "fraca"
    else:
        nivel = "muito fraca / inexistente"
    sentido = "positiva" if r > 0 else "negativa"
    return f"{nivel} e {sentido}"


def ajustar(df):
    x = df["frota_total"].to_numpy(dtype=float)
    y = df["icms_total"].to_numpy(dtype=float)

    # --- Cálculo manual -----------------------------------------------------
    x_med, y_med = x.mean(), y.mean()
    sxy = np.sum((x - x_med) * (y - y_med))
    sxx = np.sum((x - x_med) ** 2)
    syy = np.sum((y - y_med) ** 2)

    a = sxy / sxx                    # inclinação
    b = y_med - a * x_med            # intercepto
    r = sxy / np.sqrt(sxx * syy)     # correlação de Pearson

    # --- Conferência com statsmodels (MQO / OLS) ---------------------------
    ols = sm.OLS(y, sm.add_constant(x)).fit()

    return {
        "n": len(df),
        "a": a,
        "b": b,
        "r": r,
        "r2": r ** 2,
        "p_valor": ols.pvalues[1],
        "a_statsmodels": ols.params[1],
        "b_statsmodels": ols.params[0],
        "classificacao": classificar_r(r),
        "ols": ols,
    }


def prever(modelo, frota):
    """Ŷ = b + aX, com intervalo de confiança de 95% da média prevista."""
    y_hat = modelo["b"] + modelo["a"] * frota
    pred = modelo["ols"].get_prediction(np.array([[1.0, frota]])).summary_frame(alpha=0.05)
    return y_hat, float(pred["mean_ci_lower"].iloc[0]), float(pred["mean_ci_upper"].iloc[0])


if __name__ == "__main__":
    dados = carregar_dados()
    m = ajustar(dados)
    print(f"n = {m['n']} municípios")
    print(f"a (inclinação) = {m['a']:.4f}   | statsmodels: {m['a_statsmodels']:.4f}")
    print(f"b (intercepto) = {m['b']:.2f}   | statsmodels: {m['b_statsmodels']:.2f}")
    print(f"r = {m['r']:.4f} ({m['classificacao']})   R² = {m['r2']:.4f}   p = {m['p_valor']:.2e}")
    print(f"Equação: Ŷ = {m['b']:,.2f} + {m['a']:,.2f}·X")
