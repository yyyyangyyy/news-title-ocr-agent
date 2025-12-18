import streamlit as st
import cv2
import pytesseract
import re
from PIL import Image
import numpy as np
import base64
import io
import os

# ========== 页面配置 ==========
st.set_page_config(
    page_title="📰 新闻标题识别Agent",
    page_icon="📰",
    layout="wide"
)

# ========== 嵌入前端代码：监听剪贴板粘贴图片 ==========
def add_paste_image_js():
    js_code = """
    <script>
    // 监听剪贴板粘贴事件
    document.addEventListener('paste', function (e) {
        const items = (e.clipboardData || e.originalEvent.clipboardData).items;
        const pasteImages = [];
        // 遍历剪贴板中的内容，筛选图片
        for (let item of items) {
            if (item.kind === 'file' && item.type.indexOf('image/') !== -1) {
                const file = item.getAsFile();
                const reader = new FileReader();
                reader.onload = function (event) {
                    // 将图片转为Base64，传递给Streamlit的session_state
                    const base64Str = event.target.result.split(',')[1];
                    const fileName = file.name || 'paste_' + new Date().getTime() + '.png';
                    // 追加到图片列表（支持多张）
                    if (!window.pasteImages) window.pasteImages = [];
                    window.pasteImages.push({name: fileName, data: base64Str});
                    // 更新Streamlit的session_state
                    Streamlit.setComponentValue(window.pasteImages);
                };
                reader.readAsDataURL(file);
            }
        }
    });

    // 初始化Streamlit组件通信
    function initStreamlit() {
        const STREAMLIT_EVENT = 'streamlit:componentValueUpdate';
        window.Streamlit = {
            setComponentValue: function (value) {
                window.dispatchEvent(new CustomEvent(STREAMLIT_EVENT, {detail: value}));
            }
        };
    }
    initStreamlit();
    </script>
    """
    # 嵌入JS代码到页面
    st.components.v1.html(js_code, height=0)

# ========== OCR核心逻辑 ==========
class NewsTitleExtractor:
    def __init__(self):
        # 明确指定Tesseract路径（适配Streamlit Cloud）
        pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
        # OCR配置：指定中文+英文语言包
        self.ocr_config = r'--oem 3 --psm 6 -l chi_sim+eng'

    def preprocess_image(self, img_array):
        """图片预处理：提升清晰度，便于OCR识别"""
        # 转为灰度图
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        # 二值化增强对比度
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return thresh

    def extract_text_from_image(self, img_array):
        """识别图片文字"""
        processed_img = self.preprocess_image(img_array)
        text = pytesseract.image_to_string(processed_img, config=self.ocr_config)
        clean_text = re.sub(r'\n+', '\n', text).strip()
        return clean_text

    def get_news_title(self, img_array):
        """提取单张图片的新闻标题"""
        all_text = self.extract_text_from_image(img_array)
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

# ========== 工具函数：Base64转图片数组 ==========
def base64_to_img_array(base64_str):
    """将Base64字符串转为OpenCV可用的图片数组"""
    try:
        img_data = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(img_data)).convert('RGB')
        return np.array(img)
    except Exception as e:
        st.error(f"图片转换失败：{str(e)}")
        return None

# ========== 网页界面 ==========
st.title("📰 新闻标题识别Agent")
st.subheader("支持上传/粘贴图片，批量识别新闻标题")
st.divider()

# 初始化提取器
extractor = NewsTitleExtractor()

# 初始化session_state：存储粘贴的图片
if 'paste_images' not in st.session_state:
    st.session_state.paste_images = []

# 1. 嵌入粘贴图片的JS代码
add_paste_image_js()

# 2. 监听粘贴的图片数据
paste_component = st.components.v1.html(
    """
    <div id="paste-container" style="padding: 20px; border: 2px dashed #ccc; border-radius: 8px; text-align: center;">
        <p>📋 在此区域粘贴图片（支持多张），粘贴后自动加载</p>
        <p style="color: #666; font-size: 12px;">提示：可直接复制截图/图片后，按Ctrl+V（Mac按Cmd+V）粘贴</p>
    </div>
    <script>
    // 监听Streamlit组件事件，更新session_state
    document.addEventListener('streamlit:componentValueUpdate', function(e) {
        window.parent.document.querySelector('iframe[title="st.components.v1.html"]').contentWindow.Streamlit.setComponentValue(e.detail);
    });
    </script>
    """,
    height=150,
    key="paste_area"
)

# 更新session_state中的粘贴图片
if paste_component:
    st.session_state.paste_images = paste_component

# ========== 展示并处理粘贴的图片 ==========
if st.session_state.paste_images:
    st.subheader("📌 已粘贴的图片")
    paste_images_list = st.session_state.paste_images
    # 循环处理每张粘贴的图片
    for idx, img_info in enumerate(paste_images_list):
        st.markdown(f"### 图片 {idx+1}：{img_info['name']}")
        # Base64转图片数组
        img_array = base64_to_img_array(img_info['data'])
        if img_array is not None:
            # 显示图片
            st.image(img_array, caption=f"粘贴的图片 {idx+1}", width=400)
            # 识别按钮
            if st.button(f"识别图片 {idx+1} 的标题", key=f"paste_btn_{idx}"):
                with st.spinner(f"正在识别图片 {idx+1}..."):
                    result = extractor.get_news_title(img_array)
                st.success(f"图片 {idx+1} 识别完成！")
                st.markdown(f"**提取的标题**：{result['标题']}")
                with st.expander(f"查看图片 {idx+1} 全部识别文字"):
                    st.text(result['全部文字'])
    # 清空粘贴图片的按钮
    if st.button("清空所有粘贴的图片", key="clear_paste"):
        st.session_state.paste_images = []
        st.rerun()

st.divider()

# ========== 保留原有上传图片功能（支持多张上传） ==========
st.subheader("📁 上传图片识别（支持多张）")
uploaded_files = st.file_uploader(
    "选择图片（支持JPG/PNG格式，可多选）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True  # 开启多文件上传
)

if uploaded_files:
    # 循环处理每张上传的图片
    for idx, uploaded_file in enumerate(uploaded_files):
        st.markdown(f"### 上传的图片 {idx+1}：{uploaded_file.name}")
        # 显示图片
        image = Image.open(uploaded_file)
        img_array = np.array(image)
        st.image(img_array, caption=f"上传的图片 {idx+1}", width=400)
        # 识别按钮
        if st.button(f"识别上传图片 {idx+1} 的标题", key=f"upload_btn_{idx}"):
            with st.spinner(f"正在识别上传图片 {idx+1}..."):
                result = extractor.get_news_title(img_array)
            st.success(f"上传图片 {idx+1} 识别完成！")
            st.markdown(f"**提取的标题**：{result['标题']}")
            with st.expander(f"查看上传图片 {idx+1} 全部识别文字"):
                st.text(result['全部文字'])

# 页脚说明
st.divider()
st.caption("提示：1. 图片越清晰、标题文字越大，识别准确率越高；2. 粘贴多张图片时，可分次粘贴或一次性粘贴；3. 支持中文/英文标题识别")
