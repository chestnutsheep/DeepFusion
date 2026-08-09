#!/usr/bin/env node
// 热搜爬虫 - 支持抖音/微博/百度/B站/快手
// 来源：hot skill（热点数据采集），原样拷贝至本地，无需每次翻 skill 文件
// 用法:
//   node crawl-hot.js                       # 全部平台
//   node crawl-hot.js --platform=douyin     # 单平台: douyin|weibo|baidu|bilibili|kuaishou

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
const HEADERS = { 'User-Agent': UA, 'Referer': 'https://www.douyin.com/' }

// 各平台热搜接口
const PLATFORMS = {
    douyin: {
        url: 'https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/',
        parse: (json) => (json?.word_list || []).map(i => ({ rank: i.position, title: i.word, hot: i.hot_value }))
    },
    weibo: {
        url: 'https://weibo.com/ajax/side/hotSearch',
        parse: (json) => (json?.data?.realtime || []).map(i => ({ rank: i.num, title: i.word, hot: i.num }))
    },
    baidu: {
        url: 'https://top.baidu.com/api/board?platform=wise&tab=realtime',
        parse: (json) => (json?.data?.cards?.[0]?.content || []).map(i => ({ rank: i.index, title: i.word, hot: i.hotScore }))
    },
    bilibili: {
        url: 'https://api.bilibili.com/x/web-interface/wbi/search/top/realtime',
        parse: (json) => (json?.data?.list || []).map(i => ({ rank: i.position, title: i.show_name || i.keyword, hot: i.icon || '' }))
    },
    kuaishou: {
        url: 'https://www.kuaishou.com/graphql',
        method: 'POST',
        body: { operationName: 'visionHotRank', variables: { page: 1, pageSize: 30 }, query: 'query visionHotRank($page:Int,$pageSize:Int){visionHotRank(page:$page,pageSize:$pageSize){name hotScore}}' },
        parse: (json) => (json?.data?.visionHotRank || []).map((i, idx) => ({ rank: idx + 1, title: i.name, hot: i.hotScore }))
    }
}

async function fetchPlatform(name, conf) {
    try {
        const opts = { headers: HEADERS }
        if (conf.method === 'POST') {
            opts.method = 'POST'
            opts.body = JSON.stringify(conf.body)
            opts.headers['Content-Type'] = 'application/json'
        }
        const res = await fetch(conf.url, opts)
        const json = await res.json()
        return { success: true, platform: name, data: conf.parse(json) }
    } catch (e) {
        return { success: false, platform: name, error: e.message }
    }
}

async function main() {
    const args = process.argv.slice(2)
    let platform = 'all'
    for (const arg of args) {
        if (arg.startsWith('--platform=')) platform = arg.split('=')[1]
    }

    const targets = platform === 'all' ? Object.keys(PLATFORMS) : [platform]
    const now = new Date().toISOString().replace('T', ' ').substring(0, 19)
    const results = {}

    for (const name of targets) {
        const conf = PLATFORMS[name]
        if (!conf) { results[name] = { success: false, error: '不支持的平台: ' + name }; continue }
        results[name] = await fetchPlatform(name, conf)
    }

    console.log(JSON.stringify({ status: 'ok', time: now, results }, null, 2))
}

main().catch(e => {
    console.error(JSON.stringify({ status: 'error', message: e.message }))
    process.exit(1)
})
