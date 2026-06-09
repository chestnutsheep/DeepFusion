import pandas as pd
import pytest

from deep_fusion.shared.indicators import add_technical_indicators


def _sample_df(n=60):
    import numpy as np
    np.random.seed(42)
    return pd.DataFrame({
        "收盘": np.random.rand(n) * 100 + 50,
        "最低": np.random.rand(n) * 50 + 30,
        "最高": np.random.rand(n) * 50 + 70,
        "成交量": np.random.randint(1000, 10000, n),
    })


@pytest.fixture
def sample_df():
    return _sample_df()


class TestIndicators:
    def test_add_all_indicators(self, sample_df):
        add_technical_indicators(sample_df)
        expected_cols = {"MACD", "DIF", "DEA", "KDJ.K", "KDJ.D", "KDJ.J",
                         "RSI", "BOLL.U", "BOLL.M", "BOLL.L",
                         "EMA.5", "EMA.10", "EMA.20", "EMA.60",
                         "MA.5", "MA.10", "MA.20", "MA.60",
                         "WILLIAMS_R", "CCI", "OBV",
                         "ABV", "ABV.MA5", "ABV.MA10", "SAR",
                         "ROC", "PSY", "BIAS.6", "BIAS.12", "BIAS.24",
                         "MTM", "ATR14", "ADX", "DI+", "DI-"}
        for col in expected_cols:
            assert col in sample_df.columns, f"{col} missing"

    def test_empty_df(self):
        df = pd.DataFrame()
        add_technical_indicators(df)
        assert df.empty

    def test_none_df(self):
        add_technical_indicators(None)

    def test_macd_values(self, sample_df):
        add_technical_indicators(sample_df)
        col = sample_df["MACD"].dropna()
        assert len(col) > 0
        assert col.iloc[-1] != 0.0

    def test_kdj_has_values(self, sample_df):
        add_technical_indicators(sample_df)
        k = sample_df["KDJ.K"].dropna()
        assert len(k) > 0
        assert k.notna().any()

    def test_rsi_bounds(self, sample_df):
        add_technical_indicators(sample_df)
        rsi = sample_df["RSI"].dropna()
        assert rsi.between(0, 100).all()
