import base64,hashlib,io,json
from PIL import Image
from mcp.types import ImageContent
def bounded_image(block, ledger):
    if not ledger or block.type != 'image':
        return block
    raw = base64.b64decode(block.data, validate=True)
    encoded = raw
    mime = block.mimeType
    mode = 'original'
    with Image.open(io.BytesIO(raw)) as image:
        size = list(image.size)
        if len(block.data) > 200*1024:
            buffer = io.BytesIO()
            image.save(buffer, format='WEBP', lossless=True, method=4)
            encoded, mime, mode = buffer.getvalue(), 'image/webp', 'lossless'
        if len(encoded)>150*1024:
            for quality in (96,94,92,90):
                buffer=io.BytesIO()
                image.save(buffer,format='WEBP',quality=quality,method=4)
                encoded,mime,mode=buffer.getvalue(),'image/webp','WebP quality '+str(quality)
                if len(encoded)<=150*1024:
                    break
        if len(encoded) > 150*1024:
            for quality in (93,88,82,75,65,55,45):
                buffer = io.BytesIO()
                image.convert('RGB').save(buffer, format='JPEG', quality=quality, optimize=True)
                encoded, mime, mode = buffer.getvalue(), 'image/jpeg', 'JPEG quality '+str(quality)
                if len(encoded)<=150*1024:
                    break
        if len(encoded)>150*1024:
            raise ValueError('Cannot fit full GUI image within native inline budget')
    digest = hashlib.sha256
    record=dict(original_sha256=digest(raw).hexdigest(), input_bytes=len(raw), encoded_bytes=len(encoded),
                encoded_sha256=digest(encoded).hexdigest(),size=size, encoding=mode, mime=mime)
    with ledger.open('a') as f:
        f.write(json.dumps(record)+'\n')
    return ImageContent(type='image', mimeType=mime, data=base64.b64encode(encoded).decode())

