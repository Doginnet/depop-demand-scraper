import json
import re
from loguru import logger


def extract_rsc_stream(html: str) -> str:
    """Extract and reconstruct the full React Server Components (RSC) payload

    streamed via Next.js self.__next_f.push calls.
    """
    chunks: list[str] = []
    # Match self.__next_f.push([<chunk_type>, "..."])
    for m in re.finditer(
        r'self\.__next_f\.push\(\[\d+,\s*"(.*?)"\]\)', html, re.DOTALL
    ):
        raw_str = m.group(1)
        try:
            # First try standard json string decode
            decoded = json.loads(f'"{raw_str}"')
            chunks.append(decoded)
        except Exception:
            # Fallback to unicode escape decode
            try:
                decoded = raw_str.encode("utf-8").decode(
                    "unicode_escape", errors="ignore"
                )
                chunks.append(decoded)
            except Exception:
                chunks.append(raw_str)
    return "".join(chunks)


def extract_nudges(html: str) -> dict[str, int]:
    """Parse offer count and in-bag count from product page HTML.

    Returns dict with keys: 'offers_sent' and 'in_bags'.
    """
    results = {"offers_sent": 0, "in_bags": 0}

    rsc = extract_rsc_stream(html)
    target_payload = rsc if rsc else html

    # 1. Search for InBagsNudge component definition and usage
    in_bags_m = re.search(
        r'([a-zA-Z0-9]+):I\[\d+,\[[^\]]+\],"InBagsNudge"\]', target_payload
    )
    if in_bags_m:
        var_id = in_bags_m.group(1)
        usage_m = re.search(
            rf'\["\$","\$L{var_id}",null,\{{"count":(\d+)\}}\]', target_payload
        )
        if usage_m:
            try:
                results["in_bags"] = int(usage_m.group(1))
            except ValueError:
                pass
    else:
        # Fallback direct search in case RSC stream isn't reconstructed
        fallback_bag = re.search(
            r'InBagsNudge.*?count\\?":(\d+)', target_payload, re.DOTALL
        )
        if fallback_bag:
            results["in_bags"] = int(fallback_bag.group(1))

    # 2. Search for OffersSentNudge component definition and usage
    offers_m = re.search(
        r'([a-zA-Z0-9]+):I\[\d+,\[[^\]]+\],"OffersSentNudge"\]', target_payload
    )
    if offers_m:
        var_id = offers_m.group(1)
        usage_m = re.search(
            rf'\["\$","\$L{var_id}",null,\{{"count":(\d+)\}}\]', target_payload
        )
        if usage_m:
            try:
                results["offers_sent"] = int(usage_m.group(1))
            except ValueError:
                pass
    else:
        # Fallback direct search
        fallback_offers = re.search(
            r'OffersSentNudge.*?count\\?":(\d+)', target_payload, re.DOTALL
        )
        if fallback_offers:
            results["offers_sent"] = int(fallback_offers.group(1))

    logger.debug(
        f"Extracted nudges: offers_sent={results['offers_sent']}, in_bags={results['in_bags']}"
    )
    return results
