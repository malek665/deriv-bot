"""Création de publicités sur Facebook/Instagram via l'API Marketing de Meta.

Tout est créé en PAUSE : rien n'est dépensé tant que vous n'activez pas
la campagne vous-même dans le Gestionnaire de publicités.
"""

import json
import os

import requests


class MetaError(Exception):
    pass


class MetaAds:
    def __init__(self):
        self.token = os.environ.get("META_ACCESS_TOKEN", "")
        account = os.environ.get("META_AD_ACCOUNT_ID", "")
        self.account = account if account.startswith("act_") else f"act_{account}"
        self.page_id = os.environ.get("META_PAGE_ID", "")
        self.instagram_id = os.environ.get("META_INSTAGRAM_USER_ID", "")
        version = os.environ.get("META_API_VERSION", "v23.0")
        self.base = f"https://graph.facebook.com/{version}"

    def missing_config(self) -> list[str]:
        missing = []
        if not self.token:
            missing.append("META_ACCESS_TOKEN")
        if self.account == "act_":
            missing.append("META_AD_ACCOUNT_ID")
        if not self.page_id:
            missing.append("META_PAGE_ID")
        return missing

    def _post(self, path: str, data: dict | None = None, files=None) -> dict:
        payload = {k: json.dumps(v) if isinstance(v, (dict, list)) else v
                   for k, v in (data or {}).items()}
        payload["access_token"] = self.token
        try:
            r = requests.post(f"{self.base}/{path}", data=payload, files=files, timeout=60)
        except requests.RequestException as e:
            raise MetaError(f"Impossible de joindre Facebook : {e}") from e
        body = r.json() if r.content else {}
        if r.status_code >= 400 or "error" in body:
            err = body.get("error", {})
            msg = err.get("error_user_msg") or err.get("message") or r.text
            raise MetaError(f"Facebook a refusé ({path.split('/')[-1]}) : {msg}")
        return body

    def upload_image(self, filename: str, content: bytes) -> str:
        body = self._post(f"{self.account}/adimages", files={filename: (filename, content)})
        images = body.get("images", {})
        if not images:
            raise MetaError("Facebook n'a pas renvoyé l'image envoyée.")
        return next(iter(images.values()))["hash"]

    def publish(self, *, name: str, variant: dict, link: str, image: tuple[str, bytes],
                daily_budget_eur: float, countries: list[str],
                age_min: int, age_max: int) -> dict:
        """Crée campagne -> ensemble de publicités -> création -> publicité (en pause)."""
        missing = self.missing_config()
        if missing:
            raise MetaError("Configuration manquante : " + ", ".join(missing))

        image_hash = self.upload_image(*image)

        campaign = self._post(f"{self.account}/campaigns", {
            "name": name,
            "objective": "OUTCOME_TRAFFIC",
            "status": "PAUSED",
            "special_ad_categories": [],
            "is_adset_budget_sharing_enabled": "false",
        })

        platforms = ["facebook", "instagram"] if self.instagram_id else ["facebook"]
        adset = self._post(f"{self.account}/adsets", {
            "name": f"{name} - audience",
            "campaign_id": campaign["id"],
            "daily_budget": int(round(daily_budget_eur * 100)),
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "LINK_CLICKS",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "targeting": {
                "geo_locations": {"countries": countries},
                "age_min": age_min,
                "age_max": age_max,
                "publisher_platforms": platforms,
            },
            "status": "PAUSED",
        })

        story = {
            "page_id": self.page_id,
            "link_data": {
                "message": variant["primary_text"],
                "link": link,
                "name": variant["headline"],
                "description": variant["description"],
                "image_hash": image_hash,
                "call_to_action": {
                    "type": variant["call_to_action"],
                    "value": {"link": link},
                },
            },
        }
        if self.instagram_id:
            story["instagram_user_id"] = self.instagram_id

        creative = self._post(f"{self.account}/adcreatives", {
            "name": f"{name} - création",
            "object_story_spec": story,
        })

        ad = self._post(f"{self.account}/ads", {
            "name": f"{name} - pub",
            "adset_id": adset["id"],
            "creative": {"creative_id": creative["id"]},
            "status": "PAUSED",
        })

        account_num = self.account.removeprefix("act_")
        return {
            "campaign_id": campaign["id"],
            "adset_id": adset["id"],
            "creative_id": creative["id"],
            "ad_id": ad["id"],
            "manager_url": f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={account_num}",
        }
