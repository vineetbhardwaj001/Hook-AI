# app/services/ocr_service.py
import cv2
import PIL.Image

def extract_first_3s_onscreen_text(video_path: str) -> str:
    """Extract and combine text overlaid on the first 3 seconds of the video."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    
    extracted_texts = []

    # Sample 3 keyframes from 0s, 1.5s, and 3.0s
    sample_frames = [int(0 * fps), int(1.5 * fps), int(3.0 * fps)]

    for frame_idx in sample_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue
        
        # Convert frame to RGB PIL Image for OCR
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = PIL.Image.fromarray(rgb_frame)

        try:
            import pytesseract
            text = pytesseract.image_to_string(pil_img)
            clean_text = " ".join(text.split())
            if len(clean_text) > 3:
                extracted_texts.append(clean_text)
        except Exception:
            # Fallback if tesseract isn't installed locally
            pass

    cap.release()
    return " | ".join(list(set(extracted_texts)))