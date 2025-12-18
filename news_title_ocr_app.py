import streamlit as st
import cv2
import pytesseract
import re
from PIL import Image
import numpy as np

# ========== 页面配置 ==========
st.set_page_config(
    page_title="新闻标题识别Agent",
    page_icon="📰",
    layout="wide"
)

# ========== OCR核心逻辑 ==========
class NewsTitleExtractor:
    def __init__(self):
        # 配置Tesseract（适配在线环境）
        try:
            # Streamlit Cloud已预装Tesseract，无需额外配置
            pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
        except:
            pass
        self.ocr_config = r'--oem 3 --psm 6 -l chi_sim+eng'

    def preprocess_image(self, img_array):
        """图片预处理（适配Streamlit上传的图片格式）"""
        # 转为灰度图
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        # 二值化增强对比度
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return thresh

    def extract_text(self, img_array):
        """识别图片文字"""
        processed_img = self.preprocess_image(img_array)
        text = pytesseract.image_to_string(processed_img, config=self.ocr_config)
        clean_text = re.sub(r'\n+', '\n', text).strip()
        return clean_text

    def get_news_title(self, img_array):
        """提取新闻标题"""
        all_text = self.extract_text(img_array)
        if not all_text:
            return {"全部文字": "", "标题": "未识别到任何文字"}
        
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        candidate_titles = [
            line for line in lines 
            if len(line) > 4 and re.search(r'[\u4e00-\u9fff]', line)
        ]
        
        if candidate_titles:
            title = max(candidate_titles, key=len)
        else:
            title = lines[0] if lines else "无有效文字"
        
        return {
            "全部文字": all_text,
            "标题": title
        }

# ========== 网页界面 ==========
st.title("📰 新闻标题识别Agent")
st.subheader("上传包含新闻标题的图片，自动识别并提取标题")
st.divider()

# 初始化提取器
extractor = NewsTitleExtractor()

# 图片上传组件
uploaded_file = st.file_uploader(
    "选择图片（支持JPG/PNG格式）",
    type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:
    # 显示上传的图片
    st.image(uploaded_file, caption="上传的图片", width=500)
    
    # 转换图片格式（适配OpenCV）
    image = Image.open(uploaded_file)
    img_array = np.array(image)
    
    # 识别按钮
    if st.button("开始识别标题", type="primary"):
        with st.spinner("正在识别中..."):
            result = extractor.get_news_title(img_array)
        
        # 展示结果
        st.success("识别完成！")
        st.subheader("📝 提取的新闻标题")
        st.markdown(f"**{result['标题']}**")
        
        # 展开显示全部识别文字
        with st.expander("查看全部识别的文字"):
            st.text(result['全部文字'])

# 页脚说明
st.divider()
st.caption("提示：图片越清晰、标题文字越大，识别准确率越高")
