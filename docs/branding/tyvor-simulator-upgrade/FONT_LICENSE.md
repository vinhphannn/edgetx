# Ethnocentric — fixed TYVOR artwork

Nguồn: [gói chính thức Typodermic 2026i](https://typodermicfonts.com/assets/downloads/typodermic-free-fonts-2026i.zip).
Style dùng: **Ethnocentric Regular**, file `Ethnocentric Rg.otf`.

[Desktop EULA v260817, §2.2](https://typodermicfonts.com/assets/documents/Typodermic%20Desktop%20EULA%202026.pdf)
cho phép tác phẩm chữ hoàn chỉnh, cố định, không kèm font hoặc bộ ký tự có thể
lắp ghép. Asset này chỉ là một ảnh **TYVOR** duy nhất, không phải bitmap font.
OTF chỉ được đọc cục bộ khi dựng ảnh, không cài vào hệ thống, không đưa vào
firmware hoặc thư mục source phân phối. Không chia chữ thành glyph riêng.

- ZIP SHA256: `d2ea11ff669f1752eed96754ac91e38e6a77eddce748ebeb1e55b3d3222316ad`.
- Regular OTF SHA256: `cda574639d6daf582ba221f5e820c18f53370ace4f12830376721ba8bb46d9b1`.
- EULA trong ZIP và PDF chính thức có cùng SHA256:
  `e8d2e3e891a3454740e3dd9e75825878640a6cee8016f4d4ef71ab5c97774f08`.
- Bản tải/giấy phép lưu riêng trong `build-tyvor-simulator-upgrade/font-download/`
  đã gitignore. Đây là bản giao kèm giấy phép đã kiểm tra; không suy rộng quyền
  cho mọi style hoặc bản tải khác.

Bitmap: `radio/src/bitmaps/128x64/tyvor_wordmark.png`, 100×16 / 1-bit, ink bounds
(4,2)–(95,14). Nguồn dựng: `tools/render-tyvor-wordmark.py`; script chỉ xuất chữ
TYVOR cố định và yêu cầu đúng SHA256 font đã xác minh.

```sh
build-tyvor-simu/venv/bin/python tools/render-tyvor-wordmark.py \
  --font 'build-tyvor-simulator-upgrade/font-download/Ethnocentric Rg.otf' \
  --output radio/src/bitmaps/128x64/tyvor_wordmark.png
```

USB Connected trong bootloader giữ nguyên theo ràng buộc không sửa bootloader;
không tự áp dụng font mới vào màn này.
