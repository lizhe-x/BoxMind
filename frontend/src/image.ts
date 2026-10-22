/** 上传前压缩图片:最长边限到 maxEdge,导出 JPEG。顺带把 HEIC 等转成 JPEG。 */
export async function compressImage(file: Blob, maxEdge = 1600, quality = 0.82): Promise<Blob> {
  const url = URL.createObjectURL(file)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const im = new Image()
      im.onload = () => resolve(im)
      im.onerror = reject
      im.src = url
    })
    const longest = Math.max(img.width, img.height)
    const scale = longest > maxEdge ? maxEdge / longest : 1
    // 已经够小且本就是 jpeg → 原样返回
    if (scale === 1 && file.type === 'image/jpeg') return file
    const w = Math.round(img.width * scale)
    const h = Math.round(img.height * scale)
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    if (!ctx) return file
    ctx.drawImage(img, 0, 0, w, h)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
    return blob || file
  } catch {
    return file // 压缩失败 → 用原图,绝不阻断上传
  } finally {
    URL.revokeObjectURL(url)
  }
}
