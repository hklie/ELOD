#!/usr/bin/env python3
"""
Image Reader for extracting tournament rankings from JPEG images.

This module reads tournament result images (typically screenshots or photos
of result tables) and extracts player rankings using OCR.

Requires:
    - pytesseract: pip install pytesseract
    - tesseract-ocr: sudo apt-get install tesseract-ocr tesseract-ocr-spa
    - Pillow: pip install Pillow
"""

import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

try:
    from PIL import Image, ImageFilter, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False


class ImageReaderError(Exception):
    """Custom exception for image reader errors."""
    pass


@dataclass
class ImagePlayerResult:
    """Represents a player's result extracted from an image."""
    name: str
    total_score: int
    rank: int = 0


class ImageReader:
    """
    Reads tournament result images and extracts player rankings.

    The expected image format is a table with:
    - JUGADOR column: Player names as "Name Surname"
    - Round columns: 1, 2, 3, ..., N
    - TOTAL column: Total accumulated score
    - Optional: %, DIFER columns

    Players are ranked by their TOTAL score (descending).
    """

    def __init__(self, image_path: str):
        """
        Initialize the image reader.

        Args:
            image_path: Path to the JPEG image file
        """
        if not PIL_AVAILABLE:
            raise ImageReaderError(
                "Pillow not installed. Install with: pip install Pillow"
            )

        self.image_path = Path(image_path)
        if not self.image_path.exists():
            raise ImageReaderError(f"Image file not found: {image_path}")

        self.image = Image.open(self.image_path)

    def preprocess_image(self) -> Image.Image:
        """
        Preprocess the image to improve OCR accuracy.

        Returns:
            Preprocessed PIL Image
        """
        img = self.image.convert('L')  # Convert to grayscale
        img = img.filter(ImageFilter.SHARPEN)  # Sharpen
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2)  # Increase contrast
        return img

    def extract_text(self) -> str:
        """
        Extract text from the image using OCR.

        Returns:
            Extracted text as string

        Raises:
            ImageReaderError: If pytesseract is not available
        """
        if not PYTESSERACT_AVAILABLE:
            raise ImageReaderError(
                "pytesseract not installed. Install with:\n"
                "  pip install pytesseract\n"
                "  sudo apt-get install tesseract-ocr tesseract-ocr-spa"
            )

        img = self.preprocess_image()

        # Use Spanish language pack for better accent recognition
        custom_config = r'--oem 3 --psm 6 -l spa+eng'

        try:
            text = pytesseract.image_to_string(img, config=custom_config)
            return text
        except Exception as e:
            raise ImageReaderError(f"OCR failed: {e}")

    def parse_table(self, text: str) -> List[ImagePlayerResult]:
        """
        Parse extracted text to get player rankings.

        Args:
            text: Raw OCR text

        Returns:
            List of ImagePlayerResult objects sorted by score
        """
        results = []
        lines = text.strip().split('\n')

        for line in lines:
            # Skip header line and empty lines
            if not line.strip() or 'JUGADOR' in line.upper():
                continue

            # Try to extract player name and total score
            # Pattern: Name followed by numbers, with TOTAL being a larger number
            parts = line.split()
            if len(parts) < 3:
                continue

            # Find the player name (usually first 2-3 words before numbers start)
            name_parts = []
            score_parts = []
            found_numbers = False

            for part in parts:
                if re.match(r'^\d+$', part) or re.match(r'^\d+[,\.]\d+$', part):
                    found_numbers = True
                    score_parts.append(part)
                elif not found_numbers:
                    name_parts.append(part)

            if name_parts and score_parts:
                name = ' '.join(name_parts)
                # Skip MASTER row
                if name.upper() == 'MASTER':
                    continue

                # Try to find the TOTAL score (usually a 3-digit number near the end)
                total_score = 0
                for score in reversed(score_parts):
                    try:
                        val = int(score.replace(',', '').replace('.', ''))
                        if 100 <= val <= 9999:  # Likely a total score
                            total_score = val
                            break
                    except ValueError:
                        continue

                if total_score > 0:
                    results.append(ImagePlayerResult(
                        name=name,
                        total_score=total_score
                    ))

        # Sort by score descending and assign ranks
        results.sort(key=lambda x: x.total_score, reverse=True)
        for i, result in enumerate(results, 1):
            result.rank = i

        return results

    def get_rankings(self) -> List[ImagePlayerResult]:
        """
        Get player rankings from the image.

        Returns:
            List of ImagePlayerResult objects sorted by score (highest first)
        """
        text = self.extract_text()
        return self.parse_table(text)

    def get_player_names(self) -> List[str]:
        """
        Get player names in ranking order.

        Returns:
            List of player names (normalized: spaces removed)
        """
        rankings = self.get_rankings()
        return [r.name.replace(' ', '') for r in rankings]


def normalize_name(name: str) -> str:
    """
    Normalize a player name to the standard format.

    Converts "Name Surname" to "NameSurname" (no spaces).

    Args:
        name: Player name with spaces

    Returns:
        Normalized name without spaces
    """
    return name.replace(' ', '')


def create_tournament_file_from_image(image_path: str, output_path: str) -> str:
    """
    Create a tournament .txt file from an image.

    Args:
        image_path: Path to the source image
        output_path: Path for the output .txt file

    Returns:
        Path to the created file
    """
    reader = ImageReader(image_path)
    rankings = reader.get_rankings()

    with open(output_path, 'w', encoding='utf-8') as f:
        for result in rankings:
            name = normalize_name(result.name)
            f.write(f"{name}\n")

    return output_path


# Manual data entry helper for when OCR is not available
def create_tournament_from_manual_data(player_data: List[Tuple[str, int]],
                                        output_path: str) -> str:
    """
    Create a tournament file from manually entered data.

    Args:
        player_data: List of (name, total_score) tuples
        output_path: Path for the output .txt file

    Returns:
        Path to the created file
    """
    # Sort by score descending
    sorted_data = sorted(player_data, key=lambda x: x[1], reverse=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for name, score in sorted_data:
            normalized = normalize_name(name)
            f.write(f"{normalized}\n")

    return output_path


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python image_reader.py <image_path> [output_path]")
        print("\nThis tool extracts tournament rankings from JPEG images.")
        print("\nRequirements:")
        print("  pip install pytesseract Pillow")
        print("  sudo apt-get install tesseract-ocr tesseract-ocr-spa")
        sys.exit(1)

    image_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        reader = ImageReader(image_path)
        rankings = reader.get_rankings()

        print(f"Extracted {len(rankings)} players from {image_path}:\n")
        print(f"{'Rank':<6}{'Name':<30}{'Score':<10}")
        print("-" * 46)
        for r in rankings:
            print(f"{r.rank:<6}{r.name:<30}{r.total_score:<10}")

        if output_path:
            create_tournament_file_from_image(image_path, output_path)
            print(f"\nTournament file created: {output_path}")

    except ImageReaderError as e:
        print(f"Error: {e}")
        sys.exit(1)
