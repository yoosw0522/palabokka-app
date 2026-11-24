"""팔아볼까? — Streamlit 화면. AI 키는 백엔드에서만 사용합니다."""
import base64
import hashlib
import io
from pathlib import Path
import warnings

import requests
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

st.set_page_config(page_title="팔아볼까? · 중고거래 판매글 도우미", page_icon="🛍️", layout="centered")
st.markdown("""<style>
.block-container {max-width: 980px; padding-top: 2.6rem;}
h1 {letter-spacing: -.055em; font-weight: 800 !important;}
[data-testid="stCaptionContainer"] {font-size: .9rem;}
.intro {color: #456256; font-size: 1.12rem; margin-bottom: 1.3rem;}
.eyebrow {color: #176B52; font-size: .9rem; font-weight: 700; letter-spacing: .08em;}
div.stButton > button {border-radius: .7rem; min-height: 2.8rem;}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="eyebrow">물건의 다음 주인을 찾는 첫 단계</div>', unsafe_allow_html=True)
st.title("팔아볼까?")
st.markdown('<div class="intro">사진 한 장으로 시작하는 중고거래 판매글</div>', unsafe_allow_html=True)
st.write("물건이 잘 보이는 사진을 올려 주세요. 보이는 특징을 정리하고 판매글 초안을 만들어 드려요.")
st.caption("얼굴·주소·전화번호는 가리고 올려 주세요. 사진만으로 작동 여부나 가격을 판단하지 않습니다.")

try:
    API_URL = str(st.secrets["API_URL"]).strip().rstrip("/")
    ACCESS_CODE = str(st.secrets["APP_ACCESS_CODE"])
except (KeyError, FileNotFoundError):
    st.info("서비스 연결을 준비 중입니다. 관리자 설정에서 API 주소와 접근 코드를 등록해 주세요.")
    st.stop()


@st.cache_data(ttl=60, show_spinner=False)
def load_info(url):
    response = requests.get(f"{url}/", timeout=20)
    response.raise_for_status()
    info = response.json()
    if not isinstance(info.get("fields"), list) or len(info["fields"]) != 5:
        raise ValueError("API fields mismatch")
    return info


class ImageInputError(ValueError):
    """사용자에게 안내할 사진 입력 오류."""


def prepare_image(raw):
    if len(raw) > 10 * 1024 * 1024:
        raise ImageInputError("사진 파일이 10MB를 넘습니다. 파일 크기를 줄여 주세요.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as source:
            if source.width * source.height > 60_000_000:
                raise ImageInputError("사진이 6,000만 화소를 넘습니다. 해상도를 줄여 주세요.")
            if source.format not in ("JPEG", "MPO", "PNG", "WEBP"):
                raise ImageInputError("JPG·PNG·WebP 형식의 사진을 올려 주세요.")
            # 휴대폰 JPEG/MPO는 작은 크기로 디코딩한 뒤 방향을 바로잡는다.
            source.draft("RGB", (1024, 1024))
            photo = ImageOps.exif_transpose(source).convert("RGB")
            photo.thumbnail((1024, 1024))
            buffer = io.BytesIO()
            photo.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


try:
    info = load_info(API_URL)
except (requests.RequestException, ValueError, KeyError, AttributeError):
    st.error("분석 서비스에 연결하지 못했습니다. 잠시 후 새로고침해 주세요.")
    st.stop()

st.divider()
left, right = st.columns([1.05, 1], gap="large")
with left:
    st.subheader("판매할 물건을 보여 주세요")
    method = st.radio("사진 선택 방법", ["사진 올리기", "카메라로 찍기", "예시로 살펴보기"], horizontal=True)
    raw = None
    source_name = ""
    if method == "사진 올리기":
        upload = st.file_uploader("사진 파일", type=["jpg", "jpeg", "png", "webp"])
        if upload:
            raw, source_name = upload.getvalue(), upload.name
    elif method == "카메라로 찍기":
        camera = st.camera_input("물건 전체가 나오게 찍어 주세요")
        if camera:
            raw, source_name = camera.getvalue(), "카메라 사진"
    else:
        sample = Path(__file__).parent / "sample_keyboard.png"
        encoded_sample = sample.with_suffix(".b64")
        if sample.exists() or encoded_sample.exists():
            raw = sample.read_bytes() if sample.exists() else base64.b64decode(encoded_sample.read_text(encoding="ascii"))
            source_name = "연습용 키보드 그림"
            st.caption("직접 만든 연습용 그림입니다. 분석 버튼을 누르면 실제 AI에 요청합니다.")
        else:
            st.info("예시가 없습니다. 본인 물건 사진을 올려 주세요.")
    prepared = None
    if raw:
        try:
            prepared = prepare_image(raw)
            st.image(prepared, caption=source_name, use_container_width=True)
        except ImageInputError as error:
            st.error(str(error))
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            st.error("사진 해상도가 너무 큽니다. 해상도를 줄여 주세요.")
        except (ValueError, OSError, UnidentifiedImageError):
            st.error("사진 파일을 읽을 수 없습니다. JPG·PNG·WebP로 다시 저장한 뒤 올려 주세요.")
    current_id = hashlib.sha256(prepared).hexdigest() if prepared else None
    if st.session_state.get("photo_id") != current_id:
        for key in ("result", "tokens", "draft_editor"):
            st.session_state.pop(key, None)
        st.session_state["photo_id"] = current_id
    go = st.button("판매글 만들기", type="primary", use_container_width=True, disabled=prepared is None)
    st.caption("밝은 곳에서 물건 하나를 찍으면 특징을 더 정확히 읽을 수 있어요.")

with right:
    st.subheader("이렇게 정리해 드려요")
    st.write("**물건 종류와 보이는 특징**  \n사진에서 확인한 정보만 정리합니다.")
    st.write("**판매글 제목과 초안**  \n과장 없이 자연스러운 문장으로 작성합니다.")
    st.write("**판매 전 확인사항**  \n작동 상태와 거래 조건 등 직접 확인할 내용을 알려 드립니다.")

if go:
    st.session_state.pop("result", None)
    st.session_state.pop("draft_editor", None)
    with st.spinner("물건을 살펴보고 판매글을 작성하고 있어요…"):
        try:
            response = requests.post(f"{API_URL}/analyze",
                json={"image_b64": base64.b64encode(prepared).decode("ascii")},
                headers={"X-Access-Code": ACCESS_CODE}, timeout=120)
            if response.status_code != 200:
                messages = {401: "서비스 접근 설정을 확인해 주세요.", 413: "사진 크기를 줄여 다시 올려 주세요.",
                            422: "사진을 읽지 못했습니다. 다른 사진으로 시도해 주세요.",
                            429: "AI 사용 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.",
                            503: "서비스 설정을 점검 중입니다. 잠시 후 다시 시도해 주세요."}
                st.error(messages.get(response.status_code, "분석에 실패했습니다. 잠시 후 다시 시도해 주세요."))
            else:
                payload = response.json()
                result = payload["result"]
                if not isinstance(result, dict) or any(not isinstance(result.get(k), str) for k in info["fields"]):
                    raise ValueError("invalid result")
                st.session_state.result = result
                st.session_state.tokens = payload.get("tokens")
        except requests.Timeout:
            st.error("분석 시간이 길어지고 있습니다. 잠시 후 다시 시도해 주세요.")
        except (requests.RequestException, ValueError, KeyError, TypeError):
            st.error("분석 결과를 받아오지 못했습니다. 잠시 후 다시 시도해 주세요.")

if "result" in st.session_state:
    result = st.session_state.result
    st.divider()
    st.subheader("판매 준비가 한결 가벼워졌어요")
    st.table([{"항목": key, "내용": result[key]} for key in info["fields"]])
    st.caption("분석 완료 · 상태 번호 200" + (f" · 사용 토큰 {st.session_state.tokens}" if st.session_state.tokens is not None else ""))
    st.info("게시 전 실제 물건과 비교해 주세요. 가격·작동 상태·거래 장소는 직접 확인하여 작성해야 합니다.")
    draft = st.text_area("판매글을 확인하고 수정하세요", value=result["판매글 제목"] + "\n\n" + result["판매글 초안"],
                         height=220, key="draft_editor")
    st.download_button("판매글 내려받기", draft, file_name="팔아볼까_판매글.txt", mime="text/plain")
