import { describe, it, expect } from 'vitest';

// Import all configs to test
import { KITCHIN_CONFIG } from '../src/configs/kitchin';
import { JUGLAR_CONFIG } from '../src/configs/juglar';
import { KUZNETS_CONFIG } from '../src/configs/kuznets';
import { KONDRATIEV_CONFIG } from '../src/configs/kondratiev';
import { MACRO_SNAPSHOT_CONFIG } from '../src/configs/macroSnapshot';
import { GLOBAL_CONFIG } from '../src/configs/global';
import { STOCK_FINANCE_CONFIG } from '../src/configs/stockFinance';

describe('配置结构验证', () => {
  it('每个周期 config 必须有 queryKey', () => {
    const configs = [KITCHIN_CONFIG, JUGLAR_CONFIG, KUZNETS_CONFIG, KONDRATIEV_CONFIG];
    configs.forEach(cfg => expect(cfg.queryKey).toBeTruthy());
  });

  it('每个周期 config 必须有 phaseField（用于显示阶段）', () => {
    const configs = [KITCHIN_CONFIG, JUGLAR_CONFIG, KUZNETS_CONFIG, KONDRATIEV_CONFIG];
    configs.forEach(cfg => expect(cfg.phaseField).toBeTruthy());
  });

  it('每个周期 config 必须有 metrics 数组', () => {
    const configs = [KITCHIN_CONFIG, JUGLAR_CONFIG, KUZNETS_CONFIG, KONDRATIEV_CONFIG];
    configs.forEach(cfg => expect(Array.isArray(cfg.metrics)).toBe(true));
  });

  it('每个周期 config 必须有 chartSeries 数组', () => {
    const configs = [KITCHIN_CONFIG, JUGLAR_CONFIG, KUZNETS_CONFIG, KONDRATIEV_CONFIG];
    configs.forEach(cfg => expect(Array.isArray(cfg.chartSeries)).toBe(true));
  });

  describe('KITCHIN_CONFIG', () => {
    it('有正确的周期名', () => {
      expect(KITCHIN_CONFIG.title).toBe('基钦周期');
      expect(KITCHIN_CONFIG.queryKey).toBe('data_kitchin');
    });

    it('至少有 4 个 metrics', () => {
      expect(KITCHIN_CONFIG.metrics.length).toBeGreaterThanOrEqual(4);
    });

    it('metrics 都有 key 和 label', () => {
      KITCHIN_CONFIG.metrics.forEach(m => {
        expect(m.key).toBeTruthy();
        expect(m.label).toBeTruthy();
      });
    });
  });

  describe('JUGLAR_CONFIG', () => {
    it('有正确的周期名', () => {
      expect(JUGLAR_CONFIG.title).toBe('朱格拉周期');
      expect(JUGLAR_CONFIG.queryKey).toBe('data_juglar');
    });

    it('至少有 3 个 metrics', () => {
      expect(JUGLAR_CONFIG.metrics.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe('KUZNETS_CONFIG', () => {
    it('有正确的周期名', () => {
      expect(KUZNETS_CONFIG.title).toBe('库兹涅茨周期');
      expect(KUZNETS_CONFIG.queryKey).toBe('data_kuznets');
    });
  });

  describe('KONDRATIEV_CONFIG', () => {
    it('有正确的周期名', () => {
      expect(KONDRATIEV_CONFIG.title).toBe('康波周期');
      expect(KONDRATIEV_CONFIG.queryKey).toBe('data_kondratiev');
    });
  });

  describe('指标结构验证', () => {
    it('KITCHIN_CONFIG.metrics 都有 higherBetter 设置', () => {
      KITCHIN_CONFIG.metrics.forEach(m => {
        expect(m.higherBetter !== undefined).toBe(true);
      });
    });

    it('KITCHIN_CONFIG.metrics 都有 unit', () => {
      KITCHIN_CONFIG.metrics.forEach(m => {
        expect(m.unit !== undefined).toBe(true);
      });
    });
  });

  describe('快照配置', () => {
    it('MACRO_SNAPSHOT_CONFIG 是数组', () => {
      expect(Array.isArray(MACRO_SNAPSHOT_CONFIG)).toBe(true);
      expect(MACRO_SNAPSHOT_CONFIG.length).toBeGreaterThan(0);
    });

    it('每个快照指标有 source', () => {
      MACRO_SNAPSHOT_CONFIG.forEach(m => {
        expect(m.source).toBeTruthy();
      });
    });
  });

  describe('全局配置', () => {
    it('GLOBAL_CONFIG 存在且有必要的键', () => {
      expect(GLOBAL_CONFIG).toBeDefined();
      expect(GLOBAL_CONFIG.gdp).toBeDefined();
      expect(GLOBAL_CONFIG.pop).toBeDefined();
    });

    it('GDP 配置有 indicator, label, unit', () => {
      expect(GLOBAL_CONFIG.gdp.indicator).toBe('wb_gdp_growth');
      expect(GLOBAL_CONFIG.gdp.label).toBe('全球GDP增长率');
      expect(GLOBAL_CONFIG.gdp.unit).toBe('%');
    });
  });

  describe('股票配置', () => {
    it('STOCK_FINANCE_CONFIG 是数组', () => {
      expect(Array.isArray(STOCK_FINANCE_CONFIG)).toBe(true);
      expect(STOCK_FINANCE_CONFIG.length).toBeGreaterThan(0);
    });

    it('每个指标都有 key 和 label', () => {
      STOCK_FINANCE_CONFIG.forEach(m => {
        expect(m.key).toBeTruthy();
        expect(m.label).toBeTruthy();
      });
    });
  });
});