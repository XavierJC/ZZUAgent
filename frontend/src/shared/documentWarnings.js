export const pdfWarnings = {
  pdf_page_text_extraction_failed: '本页文字解析失败，已跳过；其他可读页仍保留，可对照原页查看缺失内容。',
  pdf_text_encoding_repaired: '部分字符编码已兼容处理，数学公式仍需对照原件核对。',
  text_encoding_needs_review: '部分字符无法可靠读取，以 � 标记缺失位置，请对照原件核对。',
  pdf_page_labels_unavailable: 'PDF页码标签异常，已使用原文件实际页码定位。',
  pdf_image_inspection_failed: '图片信息检查失败，已保留本页可读文字；图像内容未识别。',
}
export const documentWarning = warning => pdfWarnings[warning] || warning
