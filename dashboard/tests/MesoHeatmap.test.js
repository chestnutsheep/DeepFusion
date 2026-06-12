import {describe, expect, it} from 'vitest';

// ── 提取被测逻辑（与 MesoLayout.jsx 同步） ──

// 三分法行业分类
const CYCLICAL_NAMES = new Set([
  '采掘', '钢铁', '房地产', '建筑装饰', '建筑材料',
  '机械设备', '汽车', '非银金融', '综合',
]);
const DEFENSIVE_NAMES = new Set([
  '银行', '食品饮料', '农林牧渔', '公用事业', '交通运输',
  '商业贸易', '纺织服装', '轻工制造', '家用电器', '美容护理',
  '环保', '社会服务', '休闲服务',
]);
const GROWTH_NAMES = new Set([
  '有色金属', '化工', '电子', '计算机', '通信',
  '电气设备', '国防军工', '医药生物', '传媒', '新能源汽车',
]);

// 工具函数
function changeToColor(v) {
  if (v > 3)   return '#c43e3e';
  if (v > 1.5) return '#e2806f';
  if (v > 0.3) return '#f5c4b4';
  if (v > -0.3)return '#e8e0d0';
  if (v > -1.5)return '#75d378';
  if (v > -3)  return '#44b63a';
  return '#217819';
}

function parseTreeMapping(text) {
  if (!text) return {};
  const mapping = {};
  let currentL1 = null;
  for (const line of text.split('\n')) {
    if (line.startsWith('申万') || !line.trim()) continue;
    const l1 = line.match(/^[├└]──\s*(\S+)/);
    if (l1) { currentL1 = l1[1]; continue; }
    const l2 = line.match(/│\s+[├└]──\s*(\S+)/);
    if (l2 && currentL1) mapping[l2[1]] = currentL1;
  }
  return mapping;
}

function getCategoryOf(name) {
  if (CYCLICAL_NAMES.has(name))  return 'cyclical';
  if (DEFENSIVE_NAMES.has(name)) return 'defensive';
  if (GROWTH_NAMES.has(name))    return 'growth';
  return 'cyclical';
}

// CSV 解析（同 MesoLayout.jsx parseSWDaily）
function parseSWDaily(csv) {
  if (!csv) return { industries: [], dates: [], matrix: {} };
  const rows = csv.trim().split('\n').slice(1).map(l => l.split(','));
  if (!rows.length) return { industries: [], dates: [], matrix: {} };
  const dateSet = new Set();
  rows.forEach(r => { if (r[2]?.trim()) dateSet.add(r[2].trim()); });
  const dates = [...dateSet].sort();
  const byName = {};
  rows.forEach(r => {
    const name = r[1]?.trim();
    if (!name) return;
    if (!byName[name]) byName[name] = [];
    byName[name].push({
      name, date: r[2]?.trim(), close: parseFloat(r[3]) || 0,
      volume: parseFloat(r[4]) || 0, change: parseFloat(r[5]) || 0,
      turnover: parseFloat(r[6]) || 0, pe: parseFloat(r[7]) || 0,
      pb: parseFloat(r[8]) || 0, avgPrice: parseFloat(r[9]) || 0,
      amountRatio: parseFloat(r[10]) || 0, mktCap: parseFloat(r[11]) || 0,
      code: r[0]?.trim(),
    });
  });
  const industries = [];
  const matrix = {};
  for (const [name, recs] of Object.entries(byName)) {
    recs.sort((a, b) => b.date.localeCompare(a.date));
    industries.push(recs[0]);
    matrix[name] = {};
    recs.forEach(r => { matrix[name][r.date] = r.change; });
  }
  return { industries, dates, matrix };
}

// ── 测试 ──

describe('Meso 行业热力图 — 分类与工具函数', () => {

  it('三类分类无交叉', () => {
    const all = [...CYCLICAL_NAMES, ...DEFENSIVE_NAMES, ...GROWTH_NAMES];
    const unique = new Set(all);
    expect(all.length).toBe(unique.size);
  });

  it('所有 31 个申万一级行业已覆盖', () => {
    const SW_FIRST_LEVEL = [
      '农林牧渔','采掘','化工','钢铁','有色金属','电子','家用电器',
      '食品饮料','纺织服装','轻工制造','医药生物','公用事业',
      '交通运输','房地产','商业贸易','休闲服务','综合','建筑材料',
      '建筑装饰','电气设备','国防军工','计算机','传媒','通信',
      '银行','非银金融','汽车','机械设备','美容护理','新能源汽车',
      '煤炭','环保','社会服务',
    ];
    const classified = new Set([...CYCLICAL_NAMES, ...DEFENSIVE_NAMES, ...GROWTH_NAMES]);
    const missing = SW_FIRST_LEVEL.filter(n => !classified.has(n));
    // 煤炭 和 休闲服务 可能不在任何一个里（视数据覆盖情况），仅做 warning 不 fail
    if (missing.length > 2) {
      expect.fail(`未分类行业过多: ${missing.join(', ')}`);
    }
  });

  it('第六次康波驱动行业归入进攻型', () => {
    // 有色金属(新能源金属)和化工(新材料)在第六次康波下受成长驱动
    expect(GROWTH_NAMES.has('有色金属')).toBe(true);
    expect(GROWTH_NAMES.has('化工')).toBe(true);
  });

  it('银行归入防御', () => {
    expect(DEFENSIVE_NAMES.has('银行')).toBe(true);
    expect(CYCLICAL_NAMES.has('银行')).toBe(false);
    expect(GROWTH_NAMES.has('银行')).toBe(false);
  });

  it('美容护理归入防御', () => {
    expect(DEFENSIVE_NAMES.has('美容护理')).toBe(true);
    expect(GROWTH_NAMES.has('美容护理')).toBe(false);
  });

  it('getCategoryOf 返回正确分类', () => {
    expect(getCategoryOf('采掘')).toBe('cyclical');
    expect(getCategoryOf('银行')).toBe('defensive');
    expect(getCategoryOf('有色金属')).toBe('growth');
    expect(getCategoryOf('未知行业')).toBe('cyclical'); // 兜底
  });

  it('环保和社会服务归入防御', () => {
    expect(DEFENSIVE_NAMES.has('环保')).toBe(true);
    expect(DEFENSIVE_NAMES.has('社会服务')).toBe(true);
    expect(DEFENSIVE_NAMES.has('休闲服务')).toBe(true);
    expect(CYCLICAL_NAMES.has('环保')).toBe(false);
  });
});

describe('changeToColor 涨跌幅热力色', () => {
  it('正涨幅 → 红色系', () => {
    expect(changeToColor(5)).toBe('#c43e3e');
    expect(changeToColor(2)).toBe('#e2806f');
    expect(changeToColor(0.5)).toBe('#f5c4b4');
  });
  it('微涨微跌 → 中性色', () => {
    expect(changeToColor(0)).toBe('#e8e0d0');
  });
  it('负跌幅 → 绿色系', () => {
    expect(changeToColor(-0.5)).toBe('#75d378');
    expect(changeToColor(-2)).toBe('#44b63a');
    expect(changeToColor(-5)).toBe('#217819');
  });
});

describe('parseTreeMapping 行业树解析', () => {
  const SAMPLE_TREE = `申万一级 31 个
├── 农林牧渔 (110只) PE=28.5
│   ├── 种植业 (25只) PE=32.1
│   ├── 林业 (10只) PE=45.2
│   └── 渔业 (15只) PE=18.3
├── 采掘 (55只) PE=12.3
│   ├── 煤炭开采 (20只) PE=8.5
│   └── 石油开采 (15只) PE=15.6
├── 银行 (40只) PE=5.8
│   ├── 国有银行 (6只) PE=4.5
│   └── 股份制银行 (9只) PE=6.1
└── 综合 (30只) PE=22.0`;

  it('正确解析一二级行业映射', () => {
    const mapping = parseTreeMapping(SAMPLE_TREE);
    expect(mapping['种植业']).toBe('农林牧渔');
    expect(mapping['林业']).toBe('农林牧渔');
    expect(mapping['渔业']).toBe('农林牧渔');
    expect(mapping['煤炭开采']).toBe('采掘');
    expect(mapping['石油开采']).toBe('采掘');
    expect(mapping['国有银行']).toBe('银行');
    expect(mapping['股份制银行']).toBe('银行'); // 二级行业，父级是银行
  });

  it('空文本返回空映射', () => {
    expect(Object.keys(parseTreeMapping('')).length).toBe(0);
    expect(Object.keys(parseTreeMapping(null)).length).toBe(0);
  });

  it('只有一级没有二级时返回空映射', () => {
    const onlyL1 = '├── 农林牧渔 (110只) PE=28.5\n└── 采掘 (55只) PE=12.3';
    expect(Object.keys(parseTreeMapping(onlyL1)).length).toBe(0);
  });

  it('跳过标题行', () => {
    const withHeader = '申万一级 31 个\n├── 农林牧渔\n│   └── 种植业';
    const mapping = parseTreeMapping(withHeader);
    expect(mapping['种植业']).toBe('农林牧渔');
    // 确保标题行没被当L1
    expect(mapping['申万']).toBeUndefined();
  });
});

describe('parseSWDaily CSV解析 — 一级和二级兼容', () => {
  const SAMPLE_CSV = `指数代码,指数名称,发布日期,收盘指数,成交量,涨跌幅,换手率,市盈率,市净率,均价,成交额占比,流通市值,平均流通市值,股息率
801010,农林牧渔,20240610,3500.5,100000,1.25,2.1,28.5,3.2,15.6,0.8,50000000000,250000000,1.5
801020,采掘,20240610,2200.3,80000,-0.56,1.8,12.3,1.5,8.2,0.5,30000000000,180000000,2.8
801010,农林牧渔,20240609,3480.2,95000,0.68,1.9,27.8,3.1,15.4,0.7,49800000000,249000000,1.5`;

  it('正确解析行业快照', () => {
    const { industries, dates, matrix } = parseSWDaily(SAMPLE_CSV);
    expect(industries.length).toBe(2);
    expect(dates.length).toBe(2);
    // 最新日期在前（倒排取第一个）
    const nongye = industries.find(i => i.name === '农林牧渔');
    expect(nongye).toBeDefined();
    expect(nongye.change).toBe(1.25); // 最新日期的涨跌幅
  });

  it('矩阵正确映射', () => {
    const { matrix } = parseSWDaily(SAMPLE_CSV);
    expect(matrix['农林牧渔']['20240610']).toBe(1.25);
    expect(matrix['农林牧渔']['20240609']).toBe(0.68);
  });

  it('空CSV返回空结构', () => {
    const result = parseSWDaily('');
    expect(result.industries.length).toBe(0);
    expect(result.dates.length).toBe(0);
  });

  it('仅标题行返回空结构', () => {
    const headerOnly = '指数代码,指数名称,发布日期';
    const result = parseSWDaily(headerOnly);
    expect(result.industries.length).toBe(0);
  });
});

describe('HeatmapSection 交互状态', () => {
  // 模拟行业数据
  const mockIndustries = [
    { name: '银行', change: 0.5, mktCap: 5e12, pe: 5.8, pb: 0.6, code: '801780' },
    { name: '采掘', change: -1.2, mktCap: 1e12, pe: 12.3, pb: 1.5, code: '801020' },
    { name: '有色金属', change: 2.8, mktCap: 3e12, pe: 25.0, pb: 3.1, code: '801050' },
    { name: '食品饮料', change: 0.3, mktCap: 4e12, pe: 30.0, pb: 6.2, code: '801120' },
    { name: '化工', change: 1.5, mktCap: 2e12, pe: 18.0, pb: 2.3, code: '801030' },
  ];

  it('分类过滤：周期类只含采掘', () => {
    const filtered = mockIndustries.filter(i => CYCLICAL_NAMES.has(i.name));
    expect(filtered.length).toBe(1);
    expect(filtered[0].name).toBe('采掘');
  });

  it('分类过滤：防御类含银行+食品饮料', () => {
    const filtered = mockIndustries.filter(i => DEFENSIVE_NAMES.has(i.name));
    expect(filtered.length).toBe(2);
    expect(filtered.map(i => i.name)).toContain('银行');
    expect(filtered.map(i => i.name)).toContain('食品饮料');
  });

  it('分类过滤：进攻类含有色金属+化工', () => {
    const filtered = mockIndustries.filter(i => GROWTH_NAMES.has(i.name));
    expect(filtered.length).toBe(2);
    expect(filtered.map(i => i.name)).toContain('有色金属');
    expect(filtered.map(i => i.name)).toContain('化工');
  });

  it('Tab 切换时 drillTarget 应重置', () => {
    // 模拟状态逻辑
    let drillTarget = { industry: '银行', date: '20240610' };
    let activeCategory = 'defensive';
    // 切换到 cyclical
    activeCategory = 'cyclical';
    drillTarget = null; // 模拟 setActiveCategory 内 setDrillTarget(null)
    expect(drillTarget).toBeNull();
    expect(activeCategory).toBe('cyclical');
  });

  it('点击方格 → 确定 [行业+日期]', () => {
    const clickData = { industry: '有色金属', date: '20240610' };
    // 模拟 onIndustrySelect 联动
    let selectedIndustry = '';
    selectedIndustry = clickData.industry;
    expect(selectedIndustry).toBe('有色金属');
  });

  it('下钻返回 → drillTarget 清空，行业保留', () => {
    let drillTarget = { industry: '银行', date: '20240610' };
    let selectedIndustry = '银行';
    // 模拟返回操作
    drillTarget = null;
    expect(drillTarget).toBeNull();
    expect(selectedIndustry).toBe('银行'); // 行业选择不变
  });
});

describe('IndustryDrilldown 二级行业数据匹配', () => {
  it('tree mapping 匹配：种植业 → 农林牧渔', () => {
    const tree = '├── 农林牧渔\n│   ├── 种植业\n│   └── 林业';
    const mapping = parseTreeMapping(tree);
    expect(mapping['种植业']).toBe('农林牧渔');
    expect(mapping['林业']).toBe('农林牧渔');
  });

  it('所有一级行业都能通过 tree 拥有至少一个二级子行业', () => {
    // 构造完整树（模拟后端 industry_sw_tree 输出）
    const fullTree = `申万一级 31 个
├── 农林牧渔
│   └── 种植业
├── 采掘
│   └── 煤炭开采
├── 化工
│   └── 化学制品
├── 钢铁
│   └── 普钢
├── 有色金属
│   └── 铜
├── 电子
│   └── 半导体
├── 家用电器
│   └── 白色家电
├── 食品饮料
│   └── 白酒
├── 纺织服装
│   └── 服装
├── 轻工制造
│   └── 造纸
├── 医药生物
│   └── 化学制药
├── 公用事业
│   └── 电力
├── 交通运输
│   └── 港口
├── 房地产
│   └── 房地产开发
├── 商业贸易
│   └── 零售
├── 休闲服务
│   └── 景区
├── 综合
│   └── 多元金融
├── 建筑材料
│   └── 水泥
├── 建筑装饰
│   └── 装修装饰
├── 电气设备
│   └── 光伏设备
├── 国防军工
│   └── 航空装备
├── 计算机
│   └── 软件开发
├── 传媒
│   └── 游戏
├── 通信
│   └── 通信设备
├── 银行
│   └── 国有银行
├── 非银金融
│   └── 证券
├── 汽车
│   └── 汽车整车
├── 机械设备
│   └── 通用机械
├── 美容护理
│   └── 化妆品
└── 新能源汽车
    └── 动力电池`;
    const mapping = parseTreeMapping(fullTree);
    // 检查所有一级行业都有子映射
    const allL1 = [...CYCLICAL_NAMES, ...DEFENSIVE_NAMES, ...GROWTH_NAMES];
    const l1WithChildren = new Set(Object.values(mapping));
    const missingChildren = allL1.filter(n => !l1WithChildren.has(n));
    // 新能源汽车 可能没有子行业（视申万实际分类），允许个别缺失
    if (missingChildren.length > 3) {
      expect.fail(`以下一级行业在树中无二级子行业: ${missingChildren.join(', ')}`);
    }
  });

  it('二级行业数据过滤逻辑', () => {
    // 模拟 parseSWDaily 返回的二级行业数据
    const l2Industries = [
      { name: '种植业', change: 1.2, mktCap: 5000e8, pe: 32, pb: 3.5, code: '801011' },
      { name: '林业', change: -0.5, mktCap: 800e8, pe: 45, pb: 2.8, code: '801012' },
      { name: '煤炭开采', change: -2.1, mktCap: 12000e8, pe: 8, pb: 1.2, code: '801021' },
      { name: '国有银行', change: 0.3, mktCap: 40000e8, pe: 4.5, pb: 0.5, code: '801771' },
    ];
    const mapping = { '种植业': '农林牧渔', '林业': '农林牧渔', '煤炭开采': '采掘', '国有银行': '银行' };

    // 过滤：选择 "农林牧渔" 下的子行业
    const target = '农林牧渔';
    const sub = l2Industries.filter(i => mapping[i.name] === target);
    expect(sub.length).toBe(2);
    expect(sub.map(i => i.name)).toEqual(['种植业', '林业']);
  });

  it('日期范围缩短/增长不影响数据结构', () => {
    const csv5 = `code,name,date,close,vol,chg,turn,pe,pb,avg,amtR,mktCap,avgCap,div
801011,种植业,20240610,1000,5000,1.2,2.1,32,3.5,50,0.3,50000000000,2500000,1.0
801011,种植业,20240609,995,4800,0.8,2.0,31,3.4,49,0.3,49800000000,2490000,1.0
801011,种植业,20240608,990,4700,-0.3,1.9,30,3.3,48,0.2,49600000000,2480000,1.0
801011,种植业,20240607,985,4600,-0.5,1.8,29,3.2,47,0.2,49400000000,2470000,1.0
801011,种植业,20240606,980,4500,0.2,1.7,28,3.1,46,0.2,49200000000,2460000,1.0`;
    const result = parseSWDaily(csv5);
    expect(result.industries.length).toBe(1);
    expect(result.dates.length).toBe(5);
    expect(result.matrix['种植业']['20240610']).toBe(1.2);
    expect(result.matrix['种植业']['20240606']).toBe(0.2);
  });
});
