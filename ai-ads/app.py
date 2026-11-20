"""Mini-outil de publicité par IA : écrit les pubs avec Claude, les crée sur Facebook/Instagram."""

import json
import os

from dotenv import load_dotenv
from flask import Flask, render_template, request

from ad_writer import AdWriterError, generate_ads
from meta_ads import MetaAds, MetaError

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024  # images jusqu'à 30 Mo

ALLOWED_IMAGES = {".jpg", ".jpeg", ".png"}


def _meta_status():
    return MetaAds().missing_config()


@app.get("/")
def index():
    return render_template("index.html", form={}, meta_missing=_meta_status())


@app.post("/generate")
def generate():
    form = request.form.to_dict()
    if not form.get("business") or not form.get("product"):
        return render_template("index.html", form=form, meta_missing=_meta_status(),
                               error="Décrivez au moins votre commerce et le produit.")
    try:
        count = max(1, min(5, int(form.get("count") or 3)))
        result = generate_ads(form["business"], form["product"], form.get("audience", ""),
                              form.get("goal", ""), form.get("language") or "français", count)
    except AdWriterError as e:
        return render_template("index.html", form=form, meta_missing=_meta_status(), error=str(e))
    return render_template("index.html", form=form, result=result, meta_missing=_meta_status())


@app.post("/publish")
def publish():
    form = request.form.to_dict()
    try:
        variant = json.loads(form["variant"])
    except (KeyError, json.JSONDecodeError):
        return render_template("index.html", form={}, meta_missing=_meta_status(),
                               error="Choisissez une publicité à publier.")

    def fail(msg):
        return render_template("index.html", form={}, meta_missing=_meta_status(),
                               error=msg, published_variant=variant)

    image = request.files.get("image")
    ext = os.path.splitext(image.filename or "")[1].lower() if image else ""
    if not image or ext not in ALLOWED_IMAGES:
        return fail("Ajoutez une image JPG ou PNG pour la publicité.")
    link = form.get("link", "").strip()
    if not link.startswith(("http://", "https://")):
        return fail("Le lien doit commencer par https://")
    try:
        budget = float(form.get("budget", "5").replace(",", "."))
        age_min = int(form.get("age_min") or 18)
        age_max = int(form.get("age_max") or 65)
    except ValueError:
        return fail("Budget ou âge invalide.")
    if budget < 1:
        return fail("Le budget quotidien doit être d'au moins 1 €.")
    countries = [c.strip().upper() for c in form.get("countries", "FR").split(",") if c.strip()]

    try:
        ids = MetaAds().publish(
            name=form.get("name") or variant["headline"],
            variant=variant, link=link,
            image=(image.filename, image.read()),
            daily_budget_eur=budget, countries=countries,
            age_min=age_min, age_max=age_max,
        )
    except MetaError as e:
        return fail(str(e))
    return render_template("index.html", form={}, meta_missing=_meta_status(),
                           published=ids, published_variant=variant)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
