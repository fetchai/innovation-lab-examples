from app.models.sourcing import PartOffer


def rank_offers(offers: list[PartOffer]) -> list[PartOffer]:
    return sorted(offers, key=lambda o: (o.price_hint or "", o.title))
