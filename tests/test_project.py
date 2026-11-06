"""
test_project.py
===============
Suite de verificación completa del proyecto "Zara vs Temu - La Temporada de BBC".

Comprueba, en este orden:

    1. ESTRUCTURA      que estén todos los ficheros que pide el enunciado
    2. INGESTA         que los datos crudos cargan y tienen la forma esperada
    3. HIGIENE         que la limpieza no pierde filas en silencio
    4. FEATURES        que retornos, base 100 y máscara BBC son correctos
    5. ANÁLISIS        que los tests estadísticos devuelven lo que prometen
    6. HIPÓTESIS       que los veredictos H1/H2/H3 son los que reporta la memoria
    7. GRÁFICOS        que los 4 gráficos se construyen, también con filtros
    8. APP             que el dashboard de Streamlit arranca sin excepciones
    9. NOTEBOOKS       que memoria y sandbox están ejecutados y sin errores
   10. DOCUMENTACIÓN   que los enlaces entre documentos no están rotos

Cómo se ejecuta
---------------
    python -m pytest tests/ -v          # con detalle
    python -m pytest tests/ -q          # resumen
    python tests/test_project.py        # sin pytest instalado (modo básico)

No necesita conexión a internet: todo corre en modo `--offline` sobre la caché
de `src/data/raw/`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")   # backend sin ventana: obligatorio en CI y en tests

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402
import pandas as pd              # noqa: E402
import pytest                    # noqa: E402

# --- Hacer importable el paquete del proyecto --------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from utils import analysis, config as cfg, features, ingestion, viz  # noqa: E402
import main as pipeline                                             # noqa: E402

TOLERANCIA = 1e-9


# =============================================================================
# FIXTURES
# =============================================================================
@pytest.fixture(scope="session")
def resultados():
    """
    Ejecuta el pipeline COMPLETO una sola vez para toda la sesión de tests.

    `charts=False` mantiene los tests rápidos y, sobre todo, evita
    sobrescribir los PNG a 300 DPI que van a la presentación. Los gráficos se
    prueban aparte, construyéndolos en memoria.
    """
    return pipeline.run(offline=True, charts=False)


@pytest.fixture(scope="session")
def datos_procesados():
    """Los CSV que consume el dashboard, leídos tal cual desde disco."""
    panel = pd.read_csv(
        cfg.PROCESSED_DIR / "tidy_panel.csv", parse_dates=["Date"]
    )
    returns = panel.pivot(index="Date", columns="Ticker", values="Return")
    volume = panel.pivot(index="Date", columns="Ticker", values="Volume")
    return {
        "panel": panel,
        "returns": returns[cfg.TICKERS],
        "volume": volume[cfg.TICKERS],
    }


# =============================================================================
# 1. ESTRUCTURA DEL PROYECTO
# =============================================================================
class TestEstructura:
    """El enunciado exige una estructura de carpetas concreta."""

    @pytest.mark.parametrize(
        "ruta",
        [
            "README.md", "README.es.md", "SETUP.md", "SETUP.en.md",
            "requirements.txt", ".gitignore",
            "src/main.py", "src/app.py", "src/memoria.ipynb",
            "src/notebooks/01_sandbox.ipynb",
            "src/utils/__init__.py", "src/utils/config.py",
            "src/utils/audit.py", "src/utils/ingestion.py",
            "src/utils/features.py", "src/utils/analysis.py",
            "src/utils/viz.py",
        ],
    )
    def test_fichero_obligatorio_existe(self, ruta):
        assert (PROJECT_DIR / ruta).is_file(), f"Falta {ruta}"

    @pytest.mark.parametrize(
        "carpeta",
        ["src/data/raw", "src/data/processed", "src/notebooks", "src/utils",
         "reports/figures", "reports/tables"],
    )
    def test_carpeta_obligatoria_existe(self, carpeta):
        assert (PROJECT_DIR / carpeta).is_dir(), f"Falta la carpeta {carpeta}"

    def test_el_venv_no_se_sube_al_repositorio(self):
        gitignore = (PROJECT_DIR / ".gitignore").read_text(encoding="utf-8")
        assert ".venv" in gitignore, "El entorno virtual debe estar ignorado"

    def test_requirements_cubre_todo_lo_que_se_importa(self):
        texto = (PROJECT_DIR / "requirements.txt").read_text(encoding="utf-8")
        for libreria in ("pandas", "numpy", "matplotlib", "seaborn",
                         "yfinance", "scipy", "tabulate", "streamlit"):
            assert libreria in texto, f"{libreria} no está en requirements.txt"


# =============================================================================
# 2. INGESTA
# =============================================================================
class TestIngesta:

    def test_la_cache_cruda_existe_y_carga(self):
        precios, volumen = ingestion.load_cached()
        assert not precios.empty and not volumen.empty
        assert list(precios.columns) == cfg.TICKERS

    def test_el_extractor_soporta_ambas_orientaciones_del_multiindex(self):
        """
        yfinance cambia el orden del MultiIndex entre versiones. El extractor
        tiene que funcionar con (campo, ticker) y con (ticker, campo).
        """
        fechas = pd.date_range("2024-01-01", periods=5)
        valores = np.arange(15.0).reshape(5, 3)

        campo_ticker = pd.DataFrame(
            valores, index=fechas,
            columns=pd.MultiIndex.from_product([["Adj Close"], cfg.TICKERS]),
        )
        ticker_campo = pd.DataFrame(
            valores, index=fechas,
            columns=pd.MultiIndex.from_product([cfg.TICKERS, ["Adj Close"]]),
        )

        a = ingestion._extract_field(campo_ticker, "Adj Close", cfg.TICKERS)
        b = ingestion._extract_field(ticker_campo, "Adj Close", cfg.TICKERS)
        assert list(a.columns) == cfg.TICKERS
        assert list(b.columns) == cfg.TICKERS

    def test_falla_ruidosamente_si_falta_un_ticker(self):
        """
        El fallo silencioso más peligroso: yfinance devuelve una columna vacía
        y el análisis continúa con un universo incompleto. Debe lanzar error.
        """
        fechas = pd.date_range("2024-01-01", periods=5)
        incompleto = pd.DataFrame(
            np.ones((5, 2)), index=fechas,
            columns=pd.MultiIndex.from_product(
                [["Adj Close"], [cfg.TARGET, cfg.BENCHMARK]]
            ),
        )
        with pytest.raises(RuntimeError, match="PDD"):
            ingestion._extract_field(incompleto, "Adj Close", cfg.TICKERS)


# =============================================================================
# 3. HIGIENE DE DATOS  (el corazón de la evaluación)
# =============================================================================
class TestHigiene:

    def test_el_panel_alineado_no_tiene_nans(self, resultados):
        assert resultados["prices"].isna().sum().sum() == 0

    def test_no_se_pierde_ninguna_fila_al_alinear_calendarios(self, resultados):
        """Forward-fill conserva TODAS las sesiones; dropna habría borrado 35."""
        ledger = resultados["ledger"]
        crudas = int(ledger.loc[ledger["step"].str.startswith("A1"), "rows"].iloc[0])
        rellenadas = int(ledger.loc[ledger["step"].str.startswith("A4"), "rows"].iloc[0])
        assert crudas == rellenadas, "El ffill ha perdido filas"

    def test_un_dropna_habria_destruido_muestra(self, resultados):
        """Justifica la decisión: el coste del dropna debe ser > 0 y conocido."""
        precios_crudos, _ = ingestion.load_cached()
        perdidas = len(precios_crudos) - len(precios_crudos.dropna())
        assert perdidas > 0
        assert perdidas / len(precios_crudos) < 0.10, "Más de un 10%: revisar"

    def test_el_volumen_nunca_se_rellena(self, resultados):
        """
        Un mercado cerrado negoció CERO acciones. Si el volumen estuviera
        rellenado, H3 estaría midiendo liquidez inventada.
        """
        volumen = resultados["volume"]
        assert volumen.isna().sum().sum() > 0, (
            "El volumen no tiene NaN: se ha rellenado festivos, lo que "
            "inventaría liquidez y corrompería H3"
        )

    def test_el_ledger_registra_cada_transformacion(self, resultados):
        ledger = resultados["ledger"]
        assert len(ledger) >= 8
        for columna in ("step", "rows", "cols", "row_delta"):
            assert columna in ledger.columns

    def test_las_unicas_perdidas_de_filas_estan_justificadas(self, resultados):
        """
        Solo se admite -1 fila (el primer día no tiene t-1). Cualquier otra
        pérdida sería silenciosa y descalificaría el análisis.
        """
        ledger = resultados["ledger"]
        perdidas = ledger[ledger["row_delta"].fillna(0) < 0]
        for _, fila in perdidas.iterrows():
            assert fila["row_delta"] == -1, (
                f"Pérdida no justificada en '{fila['step']}': "
                f"{fila['row_delta']} filas"
            )

    def test_el_panel_procede_de_la_columna_ajustada(self, resultados):
        """
        Los precios analizados tienen que ser los de `adj_close_raw.csv`
        (la columna `Adj Close`), no un cierre sin ajustar.
        """
        crudos, _ = ingestion.load_cached()
        precios = resultados["prices"]
        comunes = precios.index.intersection(crudos.index)
        esperado = crudos.loc[comunes, cfg.TARGET].dropna()
        obtenido = precios.loc[esperado.index, cfg.TARGET]
        pd.testing.assert_series_equal(obtenido, esperado, check_names=False)

    def test_el_ajuste_por_dividendos_cambia_los_precios_de_verdad(self):
        """
        Comprueba sobre el payload original que `Adj Close` y `Close` NO son
        la misma serie: Inditex reparte dividendo ordinario + extraordinario,
        así que el cierre bruto va claramente por encima del ajustado.

        Si usáramos `Close`, cada fecha ex-dividendo aparecería como un falso
        desplome del ~3% y el riesgo medido de Inditex quedaría inflado - que
        es justo la magnitud que contrasta H2.
        """
        payload = cfg.RAW_DIR / "yfinance_full_payload.csv"
        if not payload.exists():
            pytest.skip(
                "El payload completo está en .gitignore (es regenerable); "
                "ejecuta `python src/main.py` para recrearlo."
            )

        crudo = pd.read_csv(payload, header=[0, 1], index_col=0, parse_dates=True)
        ajustado = crudo[("Adj Close", cfg.TARGET)]
        cierre = crudo[("Close", cfg.TARGET)]
        ratio = (cierre / ajustado).dropna()

        assert (ratio - 1).abs().max() > 0.02, (
            "'Adj Close' y 'Close' son casi idénticos: el ajuste por "
            "dividendos no se está aplicando"
        )
        assert (ratio >= 0.999).all(), (
            "El cierre bruto debería ser >= al ajustado para un valor que "
            "reparte dividendos"
        )


# =============================================================================
# 4. FEATURE ENGINEERING
# =============================================================================
class TestFeatures:

    def test_los_retornos_diarios_son_correctos(self, resultados):
        precios, retornos = resultados["prices"], resultados["returns"]
        esperado = precios[cfg.TARGET].pct_change().iloc[1:]
        pd.testing.assert_series_equal(
            retornos[cfg.TARGET], esperado, check_names=False
        )

    def test_solo_se_pierde_la_primera_fila(self, resultados):
        assert len(resultados["returns"]) == len(resultados["prices"]) - 1

    def test_el_acumulado_empieza_en_100(self, resultados):
        primera = resultados["cumulative"].iloc[0]
        assert np.allclose(primera.values, 100.0)

    def test_el_acumulado_compone_geometricamente(self, resultados):
        """+10% y luego -10% es -1%, no 0%. Suma acumulada sería un error."""
        retornos, acumulado = resultados["returns"], resultados["cumulative"]
        esperado = 100 * (1 + retornos[cfg.TARGET]).prod()
        assert abs(acumulado[cfg.TARGET].iloc[-1] - esperado) < 1e-6

    def test_la_mascara_bbc_marca_exactamente_abril_mayo_junio(self, resultados):
        featured = resultados["returns_featured"]
        meses_marcados = set(featured.loc[featured["BBC_Season"] == 1, "Month"])
        assert meses_marcados == set(cfg.BBC_MONTHS)

        meses_sin_marcar = set(featured.loc[featured["BBC_Season"] == 0, "Month"])
        assert meses_sin_marcar.isdisjoint(cfg.BBC_MONTHS)

    def test_la_mascara_bbc_es_binaria(self, resultados):
        valores = set(resultados["returns_featured"]["BBC_Season"].unique())
        assert valores <= {0, 1}

    def test_el_panel_largo_no_duplica_ni_pierde_observaciones(self, resultados):
        retornos, panel = resultados["returns"], resultados["panel"]
        assert len(panel) == retornos.shape[0] * retornos.shape[1]
        assert not panel.duplicated(subset=["Date", "Ticker"]).any()

    def test_la_mascara_de_sesiones_reales_excluye_los_dias_imputados(
        self, resultados
    ):
        genuinas = resultados["genuine"]
        assert genuinas.dtypes.eq(bool).all()
        # PDD (Nasdaq) tiene más festivos ajenos que ITX (BME).
        assert (~genuinas[cfg.COMPETITOR]).sum() > (~genuinas[cfg.TARGET]).sum()


# =============================================================================
# 5. ANÁLISIS ESTADÍSTICO
# =============================================================================
class TestAnalisis:

    def test_la_volatilidad_anualizada_usa_la_convencion_de_252_dias(
        self, resultados
    ):
        retornos = resultados["returns"][cfg.TARGET]
        esperado = 100 * retornos.std(ddof=1) * np.sqrt(252)
        obtenido = float(
            resultados["h2_risk"].loc[(cfg.TARGET, "Full period"),
                                      "Ann_volatility_%"]
        )
        assert abs(obtenido - esperado) < 1e-6

    def test_los_percentiles_de_var_son_negativos(self, resultados):
        var = resultados["h2_risk"]["VaR_5pct_daily_%"]
        assert (var < 0).all(), "El percentil 5 de los retornos debe ser negativo"

    def test_las_matrices_de_correlacion_son_validas(self, resultados):
        for clave in ("corr_season", "corr_off"):
            matriz = resultados[clave]
            assert np.allclose(np.diag(matriz), 1.0)
            assert np.allclose(matriz.values, matriz.values.T)
            assert matriz.values.min() >= -1 and matriz.values.max() <= 1

    def test_la_diferencia_de_correlaciones_es_consistente(self, resultados):
        delta = resultados["corr_season"] - resultados["corr_off"]
        pd.testing.assert_frame_equal(delta, resultados["corr_delta"])

    def test_los_p_valores_estan_en_rango(self, resultados):
        for tabla, columnas in (
            (resultados["h1_alpha"], ["p_one_sided", "Wilcoxon_p"]),
            (resultados["h2_tests"], ["Levene_p", "F_test_p_one_sided"]),
            (resultados["h3_tests"], ["Welch_p", "MannWhitney_p"]),
        ):
            for columna in columnas:
                valores = tabla[columna].dropna()
                assert ((valores >= 0) & (valores <= 1)).all(), (
                    f"p-valores fuera de [0,1] en {columna}"
                )

    def test_los_dos_regimenes_suman_la_muestra_completa(self, resultados):
        rendimiento = resultados["h1_performance"]
        total = rendimiento.xs(cfg.TARGET, level="Ticker")["N_days"].sum()
        assert total == len(resultados["returns"])

    def test_el_benchmark_se_excluye_del_analisis_de_volumen(self, resultados):
        """El 'volumen' de un índice es un agregado sintético, no acciones."""
        assert cfg.BENCHMARK not in resultados["h3_tests"].index


# =============================================================================
# 6. LOS VEREDICTOS DE LAS HIPÓTESIS
# =============================================================================
class TestHipotesis:
    """
    Blinda las conclusiones que aparecen en la memoria, el README y la
    presentación. Si alguna cambiara, estos tests avisan ANTES de la defensa.
    """

    def test_h1_no_se_cumple_porque_zara_no_bate_a_temu(self, resultados):
        alpha = resultados["h1_alpha"]
        vs_ibex = alpha.loc[(f"{cfg.TARGET} - {cfg.BENCHMARK}", cfg.BBC_LABEL)]
        vs_pdd = alpha.loc[(f"{cfg.TARGET} - {cfg.COMPETITOR}", cfg.BBC_LABEL)]

        assert vs_ibex["Mean_daily_excess_bps"] > 0, "Zara debería batir al IBEX"
        assert vs_ibex["p_one_sided"] < 0.05, "y de forma significativa"
        assert vs_pdd["Mean_daily_excess_bps"] < 0, (
            "El hallazgo clave es que Zara NO bate a Temu en temporada BBC"
        )

    def test_h2_se_cumple_zara_es_mucho_menos_volatil(self, resultados):
        completo = resultados["h2_tests"].loc["Full period"]
        assert completo["Ann_vol_ITX_%"] < completo["Ann_vol_PDD_%"]
        assert completo["Vol_ratio_PDD_over_ITX"] > 2.5
        assert completo["Levene_p"] < 0.01

    def test_h2_zara_no_tuvo_desplomes_en_temporada_bbc(self, resultados):
        fila = resultados["h2_risk"].loc[(cfg.TARGET, cfg.BBC_LABEL)]
        columna = f"Days_below_{int(100 * cfg.CRASH_THRESHOLD)}pct"
        assert fila[columna] == 0, (
            "El dato estrella de la presentación: cero sesiones por debajo "
            "del -5% durante la temporada de bodas"
        )

    def test_h2_aguanta_sin_los_dias_imputados(self, resultados):
        """La robustez es lo que responde a '¿y si tu limpieza crea el resultado?'"""
        completo = resultados["h2_tests"].loc["Full period"]
        reales = resultados["h2_tests_genuine"].loc["Full period"]
        assert reales["Ann_vol_ITX_%"] < reales["Ann_vol_PDD_%"]
        assert abs(
            completo["Vol_ratio_PDD_over_ITX"] - reales["Vol_ratio_PDD_over_ITX"]
        ) < 0.5, "La conclusión cambia al quitar los días imputados"

    def test_h3_se_cumple_el_volumen_sube_en_q2(self, resultados):
        fila = resultados["h3_tests"].loc[cfg.TARGET]
        assert fila["Uplift_%"] > 0
        assert fila["Welch_p"] < 0.05
        ganados, total = fila["Years_Q2_higher"].split("/")
        assert ganados == total, "El patrón debe repetirse todos los años"

    def test_h3_el_patron_no_aparece_en_temu(self, resultados):
        """El contraste es la prueba de que es cultural, no genérico."""
        fila = resultados["h3_tests"].loc[cfg.COMPETITOR]
        assert fila["Welch_p"] > 0.05, (
            "PDD no debería mostrar estacionalidad significativa en Q2"
        )

    def test_h3_la_subida_esta_concentrada_en_abril(self, resultados):
        """El matiz honesto que se cuenta en la memoria: junio queda por debajo."""
        mensual = resultados["h3_monthly"]
        indice = mensual[f"{cfg.TARGET}_seasonal_index"]
        assert indice.loc[4] > 1.0, "Abril debe estar por encima de la media"
        assert indice.idxmax() == 4, "Abril debe ser el máximo del año"

    def test_el_marcador_cubre_las_tres_hipotesis(self, resultados):
        veredictos = resultados["verdicts"]
        assert len(veredictos) == 3
        assert "Verdict" in veredictos.columns
        texto = " ".join(veredictos["Verdict"])
        assert "NOT SUPPORTED" in texto, "H1 debe aparecer como no cumplida"
        assert "SUPPORTED" in texto


# =============================================================================
# 7. VISUALIZACIÓN
# =============================================================================
class TestGraficos:

    def test_los_cuatro_png_existen_y_no_estan_vacios(self):
        esperados = [
            "01_H1_cumulative_returns.png",
            "02_H2_return_distributions.png",
            "03_H3_volume_seasonality.png",
            "04_SYNTHESIS_correlation_regimes.png",
        ]
        for nombre in esperados:
            ruta = cfg.FIGURES_DIR / nombre
            assert ruta.is_file(), f"Falta el gráfico {nombre}"
            assert ruta.stat().st_size > 50_000, (
                f"{nombre} pesa muy poco: ¿se ha guardado a baja resolución?"
            )

    def test_la_resolucion_de_salida_es_de_presentacion(self):
        assert cfg.FIG_DPI >= 300

    def test_cada_grafico_devuelve_una_figura_sin_escribir_en_disco(
        self, resultados
    ):
        """
        `filename=None` es lo que permite que el dashboard dibuje en vivo sin
        pisar los PNG que van al PowerPoint.
        """
        viz.apply_style()
        antes = {
            p.name: p.stat().st_mtime for p in cfg.FIGURES_DIR.glob("*.png")
        }

        constructores = [
            lambda: viz.chart1_cumulative_returns(
                resultados["cumulative"], filename=None),
            lambda: viz.chart2_return_distributions(
                resultados["panel"], filename=None),
            lambda: viz.chart3_volume_seasonality(
                resultados["h3_monthly"], filename=None),
            lambda: viz.chart4_correlation_heatmaps(
                resultados["corr_season"], resultados["corr_off"],
                resultados["corr_delta"], filename=None),
        ]
        for construir in constructores:
            figura = construir()
            assert isinstance(figura, plt.Figure)
            plt.close(figura)

        despues = {
            p.name: p.stat().st_mtime for p in cfg.FIGURES_DIR.glob("*.png")
        }
        assert antes == despues, "Dibujar en vivo ha sobrescrito los PNG"

    def test_los_graficos_funcionan_con_datos_filtrados(self, resultados):
        """Caso límite del dashboard: un solo año seleccionado."""
        viz.apply_style()
        retornos = resultados["returns"]
        un_anio = retornos[retornos.index.year == 2023]
        assert not un_anio.empty

        acumulado = (1 + un_anio).cumprod() * 100
        figura = viz.chart1_cumulative_returns(acumulado, filename=None)
        assert isinstance(figura, plt.Figure)
        plt.close(figura)

        corr_bbc, corr_off, delta = analysis.correlation_by_regime(un_anio)
        figura = viz.chart4_correlation_heatmaps(
            corr_bbc, corr_off, delta, filename=None
        )
        assert isinstance(figura, plt.Figure)
        plt.close(figura)

    def test_las_barras_de_volumen_arrancan_en_cero(self, resultados):
        """Una barra con base truncada exagera visualmente la diferencia."""
        viz.apply_style()
        figura = viz.chart3_volume_seasonality(
            resultados["h3_monthly"], filename=None
        )
        eje = figura.axes[0]
        assert eje.get_ylim()[0] == 0, "El eje Y de un gráfico de barras debe partir de 0"
        plt.close(figura)

    def test_cada_ticker_tiene_siempre_el_mismo_color(self):
        """El color sigue a la entidad, no a su posición en la leyenda."""
        assert cfg.TICKER_COLORS[cfg.TARGET] == cfg.COLORS["itx"]
        assert cfg.TICKER_COLORS[cfg.COMPETITOR] == cfg.COLORS["pdd"]
        assert len(set(cfg.TICKER_COLORS.values())) == len(cfg.TICKERS)


# =============================================================================
# 8. DASHBOARD DE STREAMLIT
# =============================================================================
class TestApp:

    @pytest.fixture(scope="class")
    @classmethod
    def app_module(cls):
        pytest.importorskip("streamlit")
        from streamlit.testing.v1 import AppTest
        return AppTest

    def test_la_app_arranca_sin_excepciones(self, app_module):
        at = app_module.from_file(str(SRC_DIR / "app.py"), default_timeout=300).run()
        assert not at.exception, [e.value for e in at.exception]
        assert len(at.tabs) == 6

    def test_el_filtro_de_anios_recalcula_las_metricas(self, app_module):
        """Lo que el usuario vio roto: los controles tienen que mover números."""
        completo = app_module.from_file(
            str(SRC_DIR / "app.py"), default_timeout=300
        ).run()
        valor_completo = completo.metric[0].value

        filtrado = app_module.from_file(
            str(SRC_DIR / "app.py"), default_timeout=300
        ).run()
        filtrado.select_slider[0].set_value((2022, 2023))
        filtrado.run()

        assert not filtrado.exception, [e.value for e in filtrado.exception]
        assert filtrado.metric[0].value != valor_completo, (
            "El filtro de años no está recalculando las métricas"
        )

    def test_el_umbral_de_desplome_recalcula_los_recuentos(self, app_module):
        at = app_module.from_file(str(SRC_DIR / "app.py"), default_timeout=300).run()
        antes = [m.value for m in at.metric]
        at.slider[0].set_value(-10.0)
        at.run()
        assert not at.exception
        assert [m.value for m in at.metric] != antes

    def test_el_modo_presentacion_no_rompe(self, app_module):
        at = app_module.from_file(str(SRC_DIR / "app.py"), default_timeout=300).run()
        at.toggle[0].set_value(False)
        at.run()
        assert not at.exception, [e.value for e in at.exception]

    def test_el_control_de_sesiones_reales_funciona(self, app_module):
        at = app_module.from_file(str(SRC_DIR / "app.py"), default_timeout=300).run()
        at.checkbox[0].set_value(True)
        at.run()
        assert not at.exception, [e.value for e in at.exception]


# =============================================================================
# 9. NOTEBOOKS
# =============================================================================
class TestNotebooks:

    @pytest.mark.parametrize(
        "ruta", ["src/memoria.ipynb", "src/notebooks/01_sandbox.ipynb"]
    )
    def test_el_notebook_es_json_valido(self, ruta):
        contenido = json.loads(
            (PROJECT_DIR / ruta).read_text(encoding="utf-8")
        )
        assert contenido["cells"], f"{ruta} no tiene celdas"

    @pytest.mark.parametrize(
        "ruta", ["src/memoria.ipynb", "src/notebooks/01_sandbox.ipynb"]
    )
    def test_el_notebook_esta_ejecutado_y_sin_errores(self, ruta):
        contenido = json.loads(
            (PROJECT_DIR / ruta).read_text(encoding="utf-8")
        )
        celdas_codigo = [
            c for c in contenido["cells"] if c["cell_type"] == "code"
        ]
        assert celdas_codigo, f"{ruta} no tiene celdas de código"

        # Señal de "esta celda se ha ejecutado". NO sirve `execution_count`:
        # algunas versiones de nbconvert lo dejan a None aunque la celda haya
        # corrido. Lo fiable es que nbclient haya dejado sus marcas de tiempo
        # en metadata['execution'], o que la celda tenga salidas.
        def ejecutada(celda: dict) -> bool:
            return bool(
                celda.get("execution_count") is not None
                or "execution" in celda.get("metadata", {})
                or celda.get("outputs")
            )

        sin_ejecutar = [c for c in celdas_codigo if not ejecutada(c)]
        assert not sin_ejecutar, (
            f"{ruta}: {len(sin_ejecutar)} celdas sin ejecutar. "
            "La memoria debe entregarse con los resultados visibles."
        )

        errores = [
            salida.get("ename")
            for celda in celdas_codigo
            for salida in celda.get("outputs", [])
            if salida.get("output_type") == "error"
        ]
        assert not errores, f"{ruta} contiene celdas con error: {errores}"

    def test_la_memoria_documenta_las_tres_hipotesis(self):
        contenido = json.loads(
            (PROJECT_DIR / "src/memoria.ipynb").read_text(encoding="utf-8")
        )
        texto = " ".join(
            "".join(c["source"])
            for c in contenido["cells"] if c["cell_type"] == "markdown"
        )
        for marca in ("H1", "H2", "H3", "Conclusiones", "Limitaciones"):
            assert marca in texto, f"La memoria no menciona '{marca}'"


# =============================================================================
# 10. DOCUMENTACIÓN
# =============================================================================
class TestDocumentacion:

    DOCS = ["README.md", "README.es.md", "SETUP.md", "SETUP.en.md"]

    @pytest.mark.parametrize("doc", DOCS)
    def test_no_hay_enlaces_internos_rotos(self, doc):
        texto = (PROJECT_DIR / doc).read_text(encoding="utf-8")
        rotos = []
        for _, destino in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", texto):
            if destino.startswith(("http", "#", "<")):
                continue
            if not (PROJECT_DIR / destino).exists():
                rotos.append(destino)
        assert not rotos, f"{doc} tiene enlaces rotos: {rotos}"

    @pytest.mark.parametrize("doc", DOCS)
    def test_las_imagenes_referenciadas_existen(self, doc):
        texto = (PROJECT_DIR / doc).read_text(encoding="utf-8")
        for src in re.findall(r'<img src="([^"]+)"', texto):
            assert (PROJECT_DIR / src).exists(), f"{doc}: falta la imagen {src}"

    def test_las_guias_explican_la_activacion_en_git_bash(self):
        """Windows + Git Bash es el caso que más falla y no es obvio."""
        for doc in ("SETUP.md", "SETUP.en.md"):
            texto = (PROJECT_DIR / doc).read_text(encoding="utf-8")
            assert "source .venv/Scripts/activate" in texto, (
                f"{doc} no documenta la activación en Git Bash"
            )

    def test_el_readme_refleja_el_veredicto_real_de_h1(self, resultados):
        """
        Blindaje contra el error más caro: que el README prometa algo que los
        datos ya no dicen. Se comprueban las dos versiones (EN principal, ES).
        """
        en = (PROJECT_DIR / "README.md").read_text(encoding="utf-8")
        es = (PROJECT_DIR / "README.es.md").read_text(encoding="utf-8")
        assert "Not supported" in en or "not supported" in en or "rejected" in en, (
            "The English README must report that H1 is not supported"
        )
        assert "No se cumple" in es or "NO se cumple" in es, (
            "El README en español debe reportar que H1 no se cumple"
        )


# =============================================================================
# EJECUCIÓN SIN PYTEST
# =============================================================================
if __name__ == "__main__":
    codigo = pytest.main([__file__, "-v", "--tb=short", "--color=yes"])
    sys.exit(codigo)
