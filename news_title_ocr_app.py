import streamlit as st
import cv2
import pytesseract
import re
from PIL import Image
import numpy as np
import base64
import io
import os
import json  # 解析JSON格式的粘贴数据

# ========== 页面基础配置 ==========
st.set_page_config(
    page_title="📰 新闻标题识别Agent",
    page_icon="📰",
    layout="wide"
)

# ========== 核心：监听剪贴板粘贴图片（修复HTML/JS格式） ==========
def add_paste_image_js():
    # 精简JS代码，避免格式错误
    js_code = '''
    <script>
    document.addEventListener('paste', function (e) {
        const items = (e.clipboardData || e.originalEvent.clipboardData).items;
        for (let item of items) {
            if (item.kind === 'file' && item.type.indexOf('image/') !== -1) {
                const file = item.getAsFile();
                const reader = new FileReader();
                reader.onload = function (event) {
                    const base64Str = event.target.result.split(',')[1];
                    const fileName = file.name || 'paste_' + new Date().getTime() + '.png';
                    const imgData = JSON.stringify({name: fileName, data: base64Str});
                    window.parent.postMessage({
                        isStreamlitMessage: true,
                        type: 'streamlit:setComponentValue',
                        value: imgData
                    }, '*');
                };
                reader.readAsDataURL(file);
            }
        }
    });
    </script>
    '''
    # 嵌入JS（高度0，无视觉占用）
    st.components.v1.html(js_code, height=0, key="paste_js")

# ========== OCR标题识别核心逻辑 ==========
class NewsTitleExtractor:
    def __init__(self):
        # 固定Tesseract路径（适配Streamlit Cloud）
        pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
        # 中英双语识别配置
        self.ocr_config = r'--oem 3 --psm 6 -l chi_sim+eng'

    def preprocess_image(self, img_array):
        """图片预处理：提升OCR识别率"""
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return thresh

    def extract_text_from_image(self, img_array):
        """识别图片中所有文字"""
        processed_img = self.preprocess_image(img_array)
        text = pytesseract.image_to_string(processed_img, config=self.ocr_config)
        return re.sub(r'\n+', '\n', text).strip()

    def get_news_title(self, img_array):
        """提取新闻标题（核心规则：最长中文行）"""
        all_text = self.extract_text_from_image(img_array)
        if not all_text:
            return {"全部文字": "", "标题": "未识别到任何文字"}
        
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        candidate_titles = [line for line in lines if len(line) > 4 and re.search(r'[\u4e00-\u9fff]', line)]
        
        title = max(candidate_titles, key=len) if candidate_titles else (lines[0] if lines else "无有效文字")
        return {"全部文字": all_text, "标题": title}

# ========== 工具函数：Base64转图片数组 ==========
def base64_to_img_array(base64_str):
    """将粘贴的Base64图片转为OpenCV可处理的数组"""
    try:
        img_data = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(img_data)).convert('RGB')
        return np.array(img)
    except Exception as e:
        st.error(f"图片转换失败：{str(e)}")
        return None

# ========== 网页界面（核心修复：HTML格式） ==========
st.title("📰 新闻标题识别Agent")
st.subheader("支持上传/粘贴图片，批量识别新闻标题")
st.divider()

# 初始化提取器和会话状态
extractor = NewsTitleExtractor()
if 'paste_images' not in st.session_state:
    st.session_state.paste_images = []

# 1. 加载粘贴图片的监听JS
add_paste_image_js()

# 2. 粘贴图片区域（修复HTML格式错误，无多余空行/引号问题）
st.components.v1.html(
    '<div id="paste-container" style="padding: 20px; border: 2px dashed #ccc; border-radius: 8px; text-align: center;">'
    '<p>📋 在此区域粘贴图片（支持多张），粘贴后自动加载</p>'
    '<p style="color: #666; font-size: 12px;">提示：复制截图后按Ctrl+V（Mac按Cmd+V）粘贴</p>'
    '</div>',
    height=150,
    key="paste_area"  # 参数名正确，无多余s
)

# 3. 处理粘贴的图片数据（容错解析）
try:
    # 捕获组件传递的图片数据
    paste_data = st.session_state.get('_component_values', {}).get('paste_area')
    if paste_data and paste_data != "null":
        img_info = json.loads(paste_data)
        # 避免重复添加
        if img_info not in st.session_state.paste_images:
            st.session_state.paste_images.append(img_info)
except:
    pass  # 解析失败时不报错，避免程序崩溃

# ========== 展示并识别粘贴的图片 ==========
if st.session_state.paste_images:
    st.subheader("📌 已粘贴的图片")
    for idx, img_info in enumerate(st.session_state.paste_images):
        st.markdown(f"### 图片 {idx+1}：{img_info['name']}")
        img_array = base64_to_img_array(img_info['data'])
        if img_array is not None:
            st.image(img_array, caption=f"粘贴的图片 {idx+1}", width=400)
            # 识别按钮
            if st.button(f"识别图片 {idx+1} 的标题", key=f"paste_btn_{idx}"):
                with st.spinner(f"正在识别图片 {idx+1}..."):
                    result = extractor.get_news_title(img_array)
                st.success(f"图片 {idx+1} 识别完成！")
                st.markdown(f"**提取的标题**：{result['标题']}")
                with st.expander(f"查看图片 {idx+1} 全部识别文字"):
                    st.text(result['全部文字'])
    # 清空按钮
    if st.button("清空所有粘贴的图片", key="clear_paste"):
        st.session_state.paste_images = []
        st.rerun()

st.divider()

# ========== 保留上传图片功能（支持多张） ==========
st.subheader("📁 上传图片识别（支持多张）")
uploaded_files = st.file_uploader(
    "选择图片（JPG/PNG格式，可多选）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if uploaded_files:
    for idx, uploaded_file in enumerate(uploaded_files):
        st.markdown(f"### 上传的图片 {idx+1}：{uploaded_file.name}")
        image = Image.open(uploaded_file)
        img_array = np.array(image)
        st.image(img_array, caption=f"上传的图片 {idx+1}", width=400)
        if st.button(f"识别上传图片 {idx+1} 的标题", key=f"upload_btn_{idx}"):
            with st.spinner(f"正在识别上传图片 {idx+1}..."):
                result = extractor.get_news_title(img_array)
            st.success(f"上传图片 {idx+1} 识别完成！")
            st.markdown(f"**提取的标题**：{result['标题']}")
            with st.expander(f"查看上传图片 {idx+1} 全部识别文字"):
                st.text(result['全部文字'])

# 页脚提示
st.divider()
st.caption("提示：图片越清晰、标题文字越大，识别准确率越高 | 支持中文/英文标题识别")
