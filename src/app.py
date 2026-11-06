"""
app.py
======
Demo interactivo (Streamlit) del EDA "Zara vs Temu - La Temporada de BBC".

Pensado como APOYO A LA PRESENTACION: cada pestaña corresponde a una hipótesis
y combina el gráfico definitivo a 300 DPI (el que irá en el PowerPoint) con
controles que permiten recalcular los números en directo delante del público.

Cómo se ejecuta:

    streamlit run src/app.py

No descarga nada de internet: lee los CSV ya procesados en src/data/processed/.
Si no existen, avisa y dice exactamente qué comando hay que lanzar antes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

# Hacer importable el paquete src/utils tanto si se lanza desde la raíz del
# proyecto como desde dentro de src/.
SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))

from utils import analysis, config as cfg, features, viz  # noqa: E402

viz.apply_style()   # misma identidad visual que los PNG del informe

# =============================================================================
# CONFIGURACIÓN DE PÁGINA
# =============================================================================
st.set_page_config(
    page_title="Zara vs Temu | La Temporada de BBC",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="expanded",
)

C = cfg.COLORS

# Estilos mínimos: tarjetas de veredicto y tipografía de las métricas.
st.markdown(
    f"""
    <style>
      .block-container {{ padding-top: 2.2rem; max-width: 1400px; }}
      .verdict-card {{
          border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 0.6rem;
          border-left: 6px solid {C['ink_muted']}; background: #f6f6f4;
      }}
      .verdict-ok   {{ border-left-color: #0ca30c; }}
      .verdict-ko   {{ border-left-color: #d03b3b; }}
      .verdict-card h4 {{ margin: 0 0 .35rem 0; font-size: 1.02rem; }}
      .verdict-card p  {{ margin: 0; font-size: .9rem; color: {C['ink_soft']}; }}
      .hero {{ font-size: 1.12rem; line-height: 1.6; color: {C['ink_soft']}; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# CARGA DE DATOS (cacheada: el demo tiene que ir fluido en directo)
# =============================================================================
@st.cache_data(show_spinner=False)
def cargar_datos() -> dict[str, pd.DataFrame]:
    """
    Lee las tablas ya procesadas por el pipeline. No hay llamadas de red aquí:
    el día de la presentación no se depende del wifi de la sala.
    """
    panel = pd.read_csv(
        cfg.PROCESSED_DIR / "tidy_panel.csv", parse_dates=["Date"]
    )
    cumulative = pd.read_csv(
        cfg.PROCESSED_DIR / "cumulative_base100.csv",
        index_col="Date",
        parse_dates=True,
    )
    prices = pd.read_csv(
        cfg.PROCESSED_DIR / "prices_aligned.csv",
        index_col="Date",
        parse_dates=True,
    )

    # Reconstruir las matrices anchas a partir del panel largo.
    returns = panel.pivot(index="Date", columns="Ticker", values="Return")
    volume = panel.pivot(index="Date", columns="Ticker", values="Volume")
    genuine = panel.pivot(
        index="Date", columns="Ticker", values="GenuineSession"
    ).astype(bool)

    orden = [t for t in cfg.TICKERS if t in returns.columns]
    return {
        "panel": panel,
        "cumulative": cumulative,
        "prices": prices,
        "returns": returns[orden],
        "volume": volume[orden],
        "genuine": genuine[orden],
    }


@st.cache_data(show_spinner=False)
def cargar_ledger() -> pd.DataFrame | None:
    ruta = cfg.TABLES_DIR / "audit_ledger.csv"
    return pd.read_csv(ruta) if ruta.exists() else None


def faltan_datos() -> bool:
    return not (cfg.PROCESSED_DIR / "tidy_panel.csv").exists()


if faltan_datos():
    st.error("### No hay datos procesados todavía")
    st.markdown(
        "Esta app solo **lee** los resultados del pipeline, no los calcula. "
        "Ejecuta una vez el pipeline y vuelve a cargar la página:"
    )
    st.code("python src/main.py", language="bash")
    st.caption(
        "Si no tienes conexión, usa `python src/main.py --offline` "
        "(necesita la caché en `src/data/raw/`)."
    )
    st.stop()

DATOS = cargar_datos()


# =============================================================================
# UTILIDADES DE PRESENTACIÓN
# =============================================================================
def mostrar_grafico(nombre: str, pie: str, construir=None) -> None:
    """
    Dibuja el gráfico de la pestaña.

    Dos modos, elegidos con el conmutador de la barra lateral:

    * **En vivo** (por defecto): llama a la MISMA función de `utils/viz.py`
      que generó el PNG del informe, pero sobre los datos ya filtrados, así
      que el gráfico responde a los controles igual que las tablas.
    * **Presentación**: muestra el PNG a 300 DPI tal cual, que es el que va al
      PowerPoint.

    Mantener una sola implementación del gráfico evita que el dashboard y la
    presentación acaben contando cosas distintas.
    """
    if graficos_en_vivo and construir is not None:
        try:
            figura = construir()
            st.pyplot(figura, width="stretch")
            plt.close(figura)
            st.caption(f"{pie}  \n*Gráfico recalculado en vivo* · {etiqueta_periodo}")
            return
        except Exception as error:                      # noqa: BLE001
            st.warning(
                f"No se ha podido dibujar el gráfico en vivo con este filtro "
                f"({error}). Se muestra la versión de presentación.",
                icon="⚠️",
            )

    ruta = cfg.FIGURES_DIR / nombre
    if ruta.exists():
        st.image(str(ruta), width="stretch")
        st.caption(f"{pie}  \n*Versión de presentación, 300 DPI · periodo completo*")
        with open(ruta, "rb") as handle:
            st.download_button(
                "⬇️ Descargar PNG a 300 DPI",
                data=handle.read(),
                file_name=nombre,
                mime="image/png",
            )
    else:
        st.warning(
            f"Falta `reports/figures/{nombre}`. Ejecuta `python src/main.py` "
            "para generar los gráficos."
        )


def tabla(df: pd.DataFrame, decimales: int = 3) -> None:
    """Muestra un DataFrame (incluido MultiIndex) de forma legible."""
    plano = df.reset_index() if isinstance(df.index, pd.MultiIndex) else df
    st.dataframe(
        plano.style.format(precision=decimales),
        width="stretch",
    )


def estilo_grafico(ax: plt.Axes) -> None:
    """Aplica la misma identidad visual que los gráficos del informe."""
    ax.set_facecolor(C["surface"])
    ax.figure.set_facecolor(C["surface"])
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(C["axis"])
    ax.grid(True, color=C["grid"], linewidth=0.7, linestyle="-")
    ax.set_axisbelow(True)
    ax.tick_params(colors=C["ink_muted"], labelsize=9)


# =============================================================================
# BARRA LATERAL — LOS CONTROLES DEL DEMO
# =============================================================================
returns_full = DATOS["returns"]
fecha_min = returns_full.index.min().date()
fecha_max = returns_full.index.max().date()

with st.sidebar:
    st.markdown("## 👗 Zara vs Temu")
    st.caption("La Temporada de BBC · EDA · The Bridge")

    st.markdown("---")
    st.markdown("### 🎛️ Controles del análisis")

    anios = sorted(returns_full.index.year.unique())
    rango = st.select_slider(
        "Años incluidos en el análisis",
        options=anios,
        value=(anios[0], anios[-1]),
        help="Recalcula TODAS las métricas. Útil para enseñar en directo que "
             "las conclusiones no dependen de un año concreto.",
    )

    umbral = st.slider(
        "Umbral de 'día de desplome' (%)",
        min_value=-12.0,
        max_value=-2.0,
        value=100 * cfg.CRASH_THRESHOLD,
        step=0.5,
        help="Define qué se considera una sesión de shock reputacional.",
    )

    solo_reales = st.checkbox(
        "Solo sesiones reales de negociación",
        value=False,
        help="Excluye los días rellenados por forward-fill (festivos del otro "
             "mercado). Sirve para demostrar que el resultado de H2 no es un "
             "artefacto de la limpieza de datos.",
    )

    graficos_en_vivo = st.toggle(
        "Gráficos en vivo",
        value=True,
        help="Activado: los gráficos se recalculan con los filtros de arriba. "
             "Desactivado: muestra los PNG a 300 DPI del informe (periodo "
             "completo), que son los que van al PowerPoint.",
    )

    st.markdown("---")
    st.markdown("### 📦 Datos")
    st.caption(
        f"**{len(returns_full)}** sesiones · "
        f"{fecha_min:%d/%m/%Y} → {fecha_max:%d/%m/%Y}  \n"
        f"Fuente: Yahoo Finance (`yfinance`)  \n"
        "Precio: `Adj Close` (ajustado por dividendos)"
    )
    st.caption(
        "Los datos se leen de `src/data/processed/`. Pulsa recargar si acabas "
        "de reejecutar `python src/main.py` en otra terminal."
    )
    if st.button("🔄 Recargar desde disco", width="stretch"):
        st.cache_data.clear()
        st.toast("Datos recargados desde src/data/processed/", icon="✅")
        st.rerun()

# --- Aplicar el filtro de años a todas las matrices --------------------------
mascara = (returns_full.index.year >= rango[0]) & (
    returns_full.index.year <= rango[1]
)
returns = returns_full.loc[mascara]
volume = DATOS["volume"].loc[mascara]
genuine = DATOS["genuine"].loc[mascara]
panel = DATOS["panel"][
    DATOS["panel"]["Date"].dt.year.between(rango[0], rango[1])
]
prices = DATOS["prices"].loc[
    (DATOS["prices"].index.year >= rango[0])
    & (DATOS["prices"].index.year <= rango[1])
]
mascara_reales = genuine if solo_reales else None
periodo_completo = tuple(rango) == (anios[0], anios[-1])
etiqueta_periodo = (
    "periodo completo 2021–2024"
    if periodo_completo
    else f"filtrado a {rango[0]}–{rango[1]}"
)

# Crecimiento base 100 recalculado sobre el tramo filtrado: si el usuario mira
# solo 2022–2023, la base 100 tiene que ser el primer día de 2022, no el de
# 2021. De lo contrario el gráfico arrancaría a media altura sin explicación.
#
# Se calcula aquí y no con features.compute_cumulative_returns() a propósito:
# esa función escribe en el ledger de auditoría, que crecería sin límite con
# cada rerun de Streamlit. La fórmula es idéntica (acumulación geométrica).
cumulative = (1.0 + returns).cumprod() * 100.0
_ancla = pd.DataFrame(
    100.0, index=[returns.index[0] - pd.Timedelta(days=1)], columns=returns.columns
)
cumulative = pd.concat([_ancla, cumulative])
cumulative.index.name = "Date"

if not periodo_completo:
    st.info(
        f"🔎 Filtro activo: **{rango[0]}–{rango[1]}**. Todo lo que ves "
        "(gráficos incluidos) está recalculado sobre ese tramo, con la base "
        "100 reanclada al primer día del periodo. Desactiva *«Gráficos en "
        "vivo»* en la barra lateral para volver a los PNG de la presentación.",
        icon="🔎",
    )


# =============================================================================
# CABECERA
# =============================================================================
st.title("¿Puede un avión chino llegar a tiempo a una boda española?")
st.markdown(
    '<p class="hero">Near-shoring ágil occidental (<b>Inditex / Zara</b>) '
    'frente al ultra-fast fashion chino transfronterizo '
    '(<b>PDD Holdings / Temu</b>), medido sobre una ventana cultural que no '
    'se puede enviar por avión: <b>la Temporada de BBC</b> — Bodas, Bautizos '
    'y Comuniones, de abril a junio.</p>',
    unsafe_allow_html=True,
)

pestanas = st.tabs([
    "📊 Resumen",
    "📈 H1 · Rendimiento",
    "⚠️ H2 · Riesgo",
    "🔊 H3 · Liquidez",
    "🔗 Síntesis",
    "🧹 Higiene de datos",
])

# =============================================================================
# PESTAÑA 1 — RESUMEN EJECUTIVO
# =============================================================================
with pestanas[0]:
    st.markdown("### Los números que sostienen el caso")

    riesgo = analysis.h2_risk_profile(returns, genuine=mascara_reales)
    itx_total = 100 * ((1 + returns[cfg.TARGET]).prod() - 1)
    pdd_total = 100 * ((1 + returns[cfg.COMPETITOR]).prod() - 1)
    vol_itx = float(riesgo.loc[(cfg.TARGET, "Full period"), "Ann_volatility_%"])
    vol_pdd = float(
        riesgo.loc[(cfg.COMPETITOR, "Full period"), "Ann_volatility_%"]
    )
    tests_vol = analysis.h3_volume_tests(volume)
    uplift = float(tests_vol.loc[cfg.TARGET, "Uplift_%"])

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Rentabilidad total · Zara", f"{itx_total:+,.1f}%")
    k2.metric("Rentabilidad total · Temu", f"{pdd_total:+,.1f}%")
    k3.metric(
        "Volatilidad anualizada",
        f"{vol_itx:.1f}% vs {vol_pdd:.1f}%",
        delta=f"Temu es {vol_pdd / vol_itx:.1f}× más volátil",
        delta_color="inverse",
    )
    k4.metric("Volumen Zara en Q2", f"{uplift:+.1f}%", delta="vs resto del año")

    st.markdown("---")
    st.markdown("### Veredicto de las tres hipótesis")
    st.caption(
        "Las tres se formularon **antes** de mirar los datos. Las tres son "
        "falsables. Una no se cumple — y es la más interesante."
    )

    alpha = analysis.h1_alpha_tests(returns)
    a_ibex = alpha.loc[(f"{cfg.TARGET} - {cfg.BENCHMARK}", cfg.BBC_LABEL)]
    a_pdd = alpha.loc[(f"{cfg.TARGET} - {cfg.COMPETITOR}", cfg.BBC_LABEL)]
    h1_ok = (
        a_ibex["Mean_daily_excess_bps"] > 0 and a_pdd["Mean_daily_excess_bps"] > 0
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"""<div class="verdict-card {'verdict-ok' if h1_ok else 'verdict-ko'}">
            <h4>{'✅' if h1_ok else '❌'} H1 · Alpha estacional</h4>
            <p>vs IBEX 35: <b>{a_ibex['Mean_daily_excess_bps']:+.1f} pb/día</b>
            (p={a_ibex['p_one_sided']:.3f})<br>
            vs Temu: <b>{a_pdd['Mean_daily_excess_bps']:+.1f} pb/día</b>
            (p={a_pdd['p_one_sided']:.3f})<br>
            <i>Exigía batir a los dos.</i></p></div>""",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""<div class="verdict-card verdict-ok">
            <h4>✅ H2 · Menor riesgo de cola</h4>
            <p>Volatilidad <b>{vol_itx:.1f}%</b> vs <b>{vol_pdd:.1f}%</b>
            ({vol_pdd / vol_itx:.1f}×)<br>
            Zara no tuvo <b>ni un solo día</b> bajo −5% en temporada BBC<br>
            <i>Levene p &lt; 0,001</i></p></div>""",
            unsafe_allow_html=True,
        )
    with c3:
        anios_ok = tests_vol.loc[cfg.TARGET, "Years_Q2_higher"]
        st.markdown(
            f"""<div class="verdict-card verdict-ok">
            <h4>✅ H3 · Liquidez estacional</h4>
            <p>Volumen Q2 <b>{uplift:+.1f}%</b> vs resto del año<br>
            Se repite en <b>{anios_ok}</b> años<br>
            <i>Matiz: concentrado en abril</i></p></div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown(
        """
### 💡 La conclusión

**El near-shoring no se cobra en rentabilidad, se cobra en ausencia de sustos.**

Zara **no** batió a Temu durante la temporada de bodas, así que H1 no se
cumple tal y como la formulamos. Pero PDD se mueve tres veces más: un activo
así puede ganar en cualquier trimestre por azar. En el periodo completo Zara
ganó un **+131,8%** y PDD perdió un **−27,7%**, con una volatilidad del
**24,9%** frente al **75,6%**. Para un comité de inversión eso no es una
diferencia de grado: es otra categoría de activo.
        """
    )

    with st.expander("📖 ¿Qué es 'La Temporada de BBC' y por qué importa?"):
        st.markdown(
            """
De abril a junio España celebra su temporada de **bodas, bautizos y
comuniones**. No es una campaña comercial más: hay código de vestimenta,
fotografías que duran décadas y una presión de etiqueta muy alta.

Eso genera tres exigencias que **un avión desde Cantón no puede satisfacer**:

1. **Tolerancia cero al retraso.** La boda es el día 12. Un paquete que llega
   el 14 vale cero.
2. **Tolerancia cero al error de talla.** La invitada necesita probarse la
   prenda; una talla equivocada no se rehace en 72 h desde China.
3. **Tolerancia cero al tejido barato.** El poliéster que transparenta en las
   fotos de la ceremonia es un coste social, no económico.

Resultado: la clienta va a la **tienda física**, se prueba la *colección de
invitada* y la recoge en 24 h — **a precio completo**. Esa es la ventaja que
el near-shoring monetiza, y lo que este análisis busca en los datos.

> **¿Por qué PDD y no Shein?** Shein es privada: no cotiza y no publica
> cuentas. PDD Holdings (Temu) es el proxy cotizado del mismo modelo
> operativo, y sí tiene serie diaria pública.
            """
        )

# =============================================================================
# PESTAÑA 2 — H1
# =============================================================================
with pestanas[1]:
    st.markdown("### H1 · Rendimiento y desacoplamiento estacional")
    st.info(
        "**Hipótesis:** durante la temporada BBC (1 abr – 30 jun), Inditex "
        "genera rentabilidad en exceso positiva **tanto** sobre el IBEX 35 "
        "**como** sobre PDD.",
        icon="🎯",
    )

    mostrar_grafico(
        "01_H1_cumulative_returns.png",
        "100 € invertidos el primer día. Las bandas doradas marcan cada "
        "temporada BBC.",
        construir=lambda: viz.chart1_cumulative_returns(cumulative, filename=None),
    )

    st.markdown("---")
    st.markdown("#### El test que de verdad contrasta H1")
    st.caption(
        "Comparar medias sueltas es débil. Construimos la serie diaria de "
        "**diferencial** (`r_Zara − r_rival`) y contrastamos si su media es "
        "positiva: al observarse ambas patas en las mismas fechas, los shocks "
        "de mercado se cancelan en lugar de inflar la varianza."
    )

    m1, m2 = st.columns(2)
    m1.metric(
        "Exceso diario vs IBEX 35 (temporada BBC)",
        f"{a_ibex['Mean_daily_excess_bps']:+.2f} pb/día",
        delta=f"p = {a_ibex['p_one_sided']:.3f}"
              + (" ✅ significativo" if a_ibex["p_one_sided"] < 0.05 else " — n.s."),
        delta_color="normal" if a_ibex["p_one_sided"] < 0.05 else "off",
    )
    m2.metric(
        "Exceso diario vs Temu (temporada BBC)",
        f"{a_pdd['Mean_daily_excess_bps']:+.2f} pb/día",
        delta=f"p = {a_pdd['p_one_sided']:.3f}"
              + (" ✅ significativo" if a_pdd["p_one_sided"] < 0.05 else " — n.s."),
        delta_color="normal" if a_pdd["p_one_sided"] < 0.05 else "off",
    )

    tabla(alpha[[
        "N_days", "Mean_daily_excess_bps", "Compounded_excess_%",
        "t_stat", "p_one_sided", "Wilcoxon_p", "Verdict",
    ]])

    st.markdown(
        """
**Cómo leerlo:** Zara bate a su mercado doméstico **solo** durante la
temporada BBC (fuera de ella el exceso no es significativo) — que es
exactamente el patrón estacional que buscábamos. Lo que no hace es batir a
Temu. H1 exigía las dos cosas, así que **no se cumple**.
        """
    )

    st.markdown("---")
    st.markdown("#### Rendimiento por régimen")
    rendimiento, cagr = analysis.h1_season_performance(returns, prices)
    tabla(rendimiento)
    st.markdown("#### Periodo completo: rentabilidad total y CAGR")
    tabla(cagr)

# =============================================================================
# PESTAÑA 3 — H2
# =============================================================================
with pestanas[2]:
    st.markdown("### H2 · Riesgo de cola y supresión de volatilidad")
    st.info(
        "**Hipótesis:** Inditex presenta menor volatilidad diaria y menos días "
        "de rentabilidad negativa extrema que PDD, por la previsibilidad del "
        "near-shoring frente a los shocks arancelarios y logísticos.",
        icon="🎯",
    )

    mostrar_grafico(
        "02_H2_return_distributions.png",
        "Las cajas muestran el comportamiento normal; los puntos son el peor "
        "5% de sesiones de cada valor, dibujados uno a uno.",
        construir=lambda: viz.chart2_return_distributions(panel, filename=None),
    )

    st.markdown("---")
    st.markdown(f"#### Días por debajo del {umbral:.1f}% (control en vivo)")
    st.caption(
        "Mueve el umbral en la barra lateral para ver cómo cambia el recuento "
        "de sesiones de shock. El contraste se mantiene en todo el rango."
    )

    cols = st.columns(3)
    for col, ticker in zip(cols, returns.columns):
        serie = returns[ticker]
        if solo_reales:
            serie = serie.where(genuine[ticker])
        serie = serie.dropna()
        n_shock = int((serie < umbral / 100).sum())
        col.metric(
            cfg.LABELS[ticker],
            f"{n_shock} sesiones",
            delta=f"{100 * n_shock / len(serie):.1f}% del periodo",
            delta_color="off",
        )

    st.markdown("---")
    st.markdown("#### Huella de riesgo completa")
    st.caption(
        "Cuatro estadísticos, no solo la volatilidad: la desviación típica "
        "resume, pero esconde justo la parte que duele. La **asimetría** dice "
        "si los movimientos grandes son subidas o desplomes; la **curtosis**, "
        "cuán gruesas son las colas; el **percentil 5** es el proxy histórico "
        "de Value-at-Risk: *en el peor día de cada 20, ¿cuánto pierdo?*"
    )
    tabla(riesgo)

    st.markdown("#### Tests de igualdad de varianzas (Zara vs Temu)")
    tabla(analysis.h2_variance_tests(returns, genuine=mascara_reales))
    st.caption(
        "Se usa **Levene centrado en la mediana** (Brown-Forsythe): a "
        "diferencia del test de Bartlett, es robusto frente a las colas "
        "gruesas de las rentabilidades diarias."
    )

    if not solo_reales:
        st.success(
            "💡 **Para la defensa:** activa *«Solo sesiones reales»* en la "
            "barra lateral. Excluye los días rellenados por forward-fill y la "
            "ratio de volatilidad apenas se mueve — prueba de que el resultado "
            "es una propiedad de las empresas, no de nuestra limpieza.",
            icon="💡",
        )
    else:
        st.success(
            "✅ Estás viendo **solo sesiones reales**: sin ningún día imputado, "
            "la conclusión de H2 no cambia.",
            icon="✅",
        )

# =============================================================================
# PESTAÑA 4 — H3
# =============================================================================
with pestanas[3]:
    st.markdown("### H3 · Liquidez estacional y convicción del mercado")
    st.info(
        "**Hipótesis:** el volumen de negociación de Inditex muestra un "
        "incremento consistente y predecible en Q2 (abril–junio), reflejando "
        "el posicionamiento institucional antes de la venta estacional a "
        "precio completo.",
        icon="🎯",
    )

    mensual, anual = analysis.h3_volume_seasonality(volume)

    mostrar_grafico(
        "03_H3_volume_seasonality.png",
        "Volumen medio diario por mes natural. Los meses BBC en dorado, con "
        "base cero obligatoria.",
        construir=lambda: viz.chart3_volume_seasonality(mensual, filename=None),
    )

    st.markdown("---")

    elegido = st.radio(
        "Comparar el perfil mensual de:",
        options=cfg.VOLUME_TICKERS,
        format_func=lambda t: cfg.LABELS[t],
        horizontal=True,
    )

    fig, ax = plt.subplots(figsize=(11, 4))
    valores = mensual[f"{elegido}_avg_volume"].astype(float) / 1e6
    colores = [
        C["season"] if bbc else C["neutral_bar"]
        for bbc in mensual["Is_BBC_month"]
    ]
    ax.bar(mensual["Month_name"], valores, color=colores, width=0.74, zorder=3)
    ax.axhline(valores.mean(), color=C["ink_muted"], linewidth=1.2, zorder=4)
    ax.set_ylim(bottom=0)                       # base cero, siempre
    ax.set_ylabel("Millones de acciones/día", fontsize=10, fontweight="bold")
    ax.set_title(
        f"{cfg.LABELS[elegido]} · volumen medio diario por mes",
        fontsize=12, fontweight="bold", color=C["ink"],
    )
    estilo_grafico(ax)
    ax.grid(axis="x", visible=False)
    st.pyplot(fig, width="stretch")
    plt.close(fig)

    if elegido == cfg.COMPETITOR:
        st.caption(
            "El contraste es el que predecía la tesis cultural: PDD **no** "
            "tiene pico en abril. Su calendario lo marcan el Singles' Day y el "
            "Black Friday, no una comunión en Valladolid."
        )
    else:
        st.caption(
            "Abril es el mes de mayor negociación del año. Pero ojo al matiz: "
            "**junio queda por debajo de la media anual** — el dinero "
            "institucional se adelanta al pico de ventas, no lo acompaña."
        )

    st.markdown("---")
    st.markdown("#### Contraste Q2 vs resto del año")
    tabla(tests_vol)
    st.caption(
        "Se añade Mann-Whitney porque el volumen está muy sesgado a la derecha "
        "(unos pocos días de resultados y rebalanceos son enormes) y la media "
        "sola es frágil. **Años con Q2 superior** es el control de "
        "consistencia: un patrón 4/4 es una afirmación de negocio muy distinta "
        "de una que depende de un año afortunado."
    )

    st.markdown("#### ¿Se repite todos los años? (volumen medio Inditex)")
    st.dataframe(
        anual.style.format("{:,.0f}").background_gradient(
            cmap="Blues", axis=None
        ),
        width="stretch",
    )

# =============================================================================
# PESTAÑA 5 — SÍNTESIS
# =============================================================================
with pestanas[4]:
    st.markdown("### Síntesis · Regímenes de correlación")
    st.caption(
        "Una matriz de correlación responde a *«¿se mueven como un solo "
        "animal o como tres?»*. Si la tesis cultural se cumple, Zara debería "
        "desacoplarse justo dentro de la ventana abril–junio."
    )

    corr_bbc, corr_off, delta = analysis.correlation_by_regime(returns)

    mostrar_grafico(
        "04_SYNTHESIS_correlation_regimes.png",
        "Los dos primeros paneles comparten escala para poder compararlos; el "
        "tercero mide un cambio de correlación y lleva su propia escala, "
        "etiquetada explícitamente.",
        construir=lambda: viz.chart4_correlation_heatmaps(
            corr_bbc, corr_off, delta, filename=None
        ),
    )

    st.markdown("---")

    d_ibex = float(delta.loc[cfg.TARGET, cfg.BENCHMARK])
    d_pdd = float(delta.loc[cfg.TARGET, cfg.COMPETITOR])
    q1, q2 = st.columns(2)
    q1.metric(
        "Correlación Zara ↔ IBEX 35",
        f"{corr_bbc.loc[cfg.TARGET, cfg.BENCHMARK]:.2f} en temporada",
        delta=f"{d_ibex:+.2f} vs fuera de temporada",
        delta_color="inverse",
    )
    q2.metric(
        "Correlación Zara ↔ Temu",
        f"{corr_bbc.loc[cfg.TARGET, cfg.COMPETITOR]:.2f} en temporada",
        delta=f"{d_pdd:+.2f} vs fuera de temporada",
        delta_color="off",
    )

    e1, e2, e3 = st.columns(3)
    for col, (titulo, matriz) in zip(
        (e1, e2, e3),
        [
            ("Temporada BBC", corr_bbc),
            ("Fuera de temporada", corr_off),
            ("Diferencia", delta),
        ],
    ):
        col.markdown(f"**{titulo}**")
        col.dataframe(
            matriz.style.format("{:+.2f}").background_gradient(
                cmap="RdBu", vmin=-1, vmax=1, axis=None
            ),
            width="stretch",
        )

    st.markdown(
        f"""
#### El hallazgo que no buscábamos

Zara **se desacopla de su propio mercado** durante la temporada BBC: su
correlación con el IBEX 35 cae **{d_ibex:+.2f}**. Durante abril–junio Inditex
deja de comportarse como «una acción española más» y responde a su propio
motor comercial.

Lo que **no** ocurre es un desacoplamiento frente a Temu — pero es que la
correlación con PDD ya era baja todo el año: dos mercados, dos divisas y dos
husos horarios. No había nada de lo que desacoplarse.
        """
    )

# =============================================================================
# PESTAÑA 6 — HIGIENE DE DATOS
# =============================================================================
with pestanas[5]:
    st.markdown("### Higiene de datos · la trazabilidad completa")
    st.caption(
        "Lo que más puede tumbar un proyecto de datos es perder filas sin "
        "darse cuenta. Aquí cada transformación queda auditada."
    )

    ledger = cargar_ledger()
    if ledger is not None:
        st.markdown("#### Ledger de auditoría: forma del dataset en cada paso")
        st.dataframe(ledger, width="stretch", hide_index=True)
        st.caption(
            "Las dos únicas variaciones de tamaño están justificadas: "
            "**−1 fila** en los retornos (el primer día no tiene `t−1`) y "
            "**+1** en el acumulado (el ancla base 100)."
        )

    st.markdown("---")
    d1, d2 = st.columns(2)
    with d1:
        st.markdown(
            """
#### 1 · `Adj Close`, no `Close`

Inditex reparte dividendo ordinario **más** extraordinario cada año. Sobre el
cierre bruto, cada fecha ex-dividendo aparece como un desplome del ~3% que
nunca ocurrió.

Eso habría **inflado artificialmente el riesgo de Inditex** — justo lo que
mide H2. Habríamos suspendido nuestra propia hipótesis por un error de datos.

#### 2 · Forward-fill, nunca `.dropna()`

Madrid y Nueva York no comparten festivos. Un `.dropna()` general habría
destruido **35 filas (3,5% de la muestra)**.

Y el sesgo no sería aleatorio: **la Semana Santa cae siempre en marzo/abril**,
justo en el borde de la ventana que estudiamos.
            """
        )
    with d2:
        st.markdown(
            """
#### 3 · El volumen NO se rellena

Un mercado cerrado negoció **cero** acciones. Arrastrar la sesión de ayer a un
festivo inventaría liquidez — precisamente la magnitud que mide H3.

Los festivos se dejan como `NaN` y las medias mensuales usan solo sesiones
reales.

#### 4 · Control de robustez del ffill

Cada día rellenado produce un retorno de 0,00%, y los ceros reducen la
desviación típica. Como H2 afirma que Zara es *menos* volátil, **H2 se calcula
dos veces**.

→ Pruébalo con el check *«Solo sesiones reales»* de la barra lateral.
            """
        )

    st.markdown("---")
    st.markdown("#### Sesiones reales vs imputadas por ticker")
    resumen_ffill = pd.DataFrame({
        "Sesiones totales": len(genuine),
        "Sesiones reales": genuine.sum(),
        "Días imputados (ffill)": (~genuine).sum(),
        "% imputado": (100 * (~genuine).mean()).round(2),
    })
    resumen_ffill.index.name = "Ticker"
    st.dataframe(resumen_ffill, width="stretch")

    st.markdown("---")
    st.markdown("#### Descargar los datos procesados")
    f1, f2 = st.columns(2)
    with f1:
        st.download_button(
            "⬇️ Panel completo (tidy_panel.csv)",
            data=panel.to_csv(index=False).encode("utf-8"),
            file_name="tidy_panel.csv",
            mime="text/csv",
            width="stretch",
        )
    with f2:
        st.download_button(
            "⬇️ Rentabilidades diarias (CSV)",
            data=returns.to_csv().encode("utf-8"),
            file_name="daily_returns.csv",
            mime="text/csv",
            width="stretch",
        )

# =============================================================================
# PIE
# =============================================================================
st.markdown("---")
st.caption(
    "EDA · Módulo Data Analysis · Bootcamp Data Science (The Bridge) · "
    "Datos: Yahoo Finance vía `yfinance` · "
    "Código: `src/utils/` · Memoria: `src/memoria.ipynb`"
)
