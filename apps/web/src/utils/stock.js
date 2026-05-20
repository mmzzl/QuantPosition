export function getStockName(code) {
  return new Promise((resolve) => {
    const sinaCode = code.startsWith('6') ? `sh${code}` : `sz${code}`
    const url = `http://hq.sinajs.cn/list=${sinaCode}`

    fetch(url)
      .then(response => response.text())
      .then(text => {
        const match = text.match(/="([^"]+)"/)
        if (match) {
          const data = match[1].split(',')
          if (data[0]) {
            resolve(data[0])
            return
          }
        }
        resolve(null)
      })
      .catch(() => resolve(null))
  })
}

export function getStockPrice(code) {
  return new Promise((resolve) => {
    const sinaCode = code.startsWith('6') ? `sh${code}` : `sz${code}`
    const url = `http://hq.sinajs.cn/list=${sinaCode}`

    fetch(url)
      .then(response => response.text())
      .then(text => {
        const match = text.match(/="([^"]+)"/)
        if (match) {
          const data = match[1].split(',')
          if (data[1]) {
            resolve(parseFloat(data[1]))
            return
          }
        }
        resolve(null)
      })
      .catch(() => resolve(null))
  })
}