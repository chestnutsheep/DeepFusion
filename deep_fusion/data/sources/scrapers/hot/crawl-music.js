#!/usr/bin/env node
// 音乐热榜爬虫 - 支持 QQ音乐/网易云/酷狗/酷我
// 来源：hot skill（热点数据采集），原样拷贝至本地
// 用法:
//   node crawl-music.js                      # 全部平台
//   node crawl-music.js --platform=qq        # 单平台: qq|netease|kugou|kuwo

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'

const PLATFORMS = {
    qq: {
        url: 'https://c.y.qq.com/v8/fcg-bin/fcg_v8_toplist_cp.fcg?tpl=3&page=detail&date=2024&topid=4&type=top&song_begin=0&song_num=30&g_tk=5381&loginUin=0&hostUin=0&format=jsonp&inCharset=utf8&outCharset=utf-8&notice=0&platform=yqq.json&needNewCode=0',
        parse: (json) => (json?.songlist || []).map((i, idx) => ({ rank: idx + 1, title: i.data.songname, artist: i.data.singer?.[0]?.name || '' }))
    },
    netease: {
        url: 'https://music.163.com/api/playlist/detail?id=3778678',
        parse: (json) => (json?.result?.tracks || []).map((i, idx) => ({ rank: idx + 1, title: i.name, artist: i.artists?.[0]?.name || '' }))
    },
    kugou: {
        url: 'https://www.kugou.com/yy/rank/home/1-23784.html',
        parse: () => []
    },
    kuwo: {
        url: 'https://www.kuwo.cn/api/www/bang/bang/musicList?bangId=93&pn=1&rn=30',
        parse: (json) => (json?.data?.musicList || []).map((i, idx) => ({ rank: idx + 1, title: i.name, artist: i.artist || '' }))
    }
}

async function fetchPlatform(name, conf) {
    try {
        const res = await fetch(conf.url, { headers: { 'User-Agent': UA } })
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
