from flask import (Flask, render_template, request, redirect, url_for, flash, session)
from flask_mysqldb import MySQL
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import re
import time
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

app.config['MYSQL_HOST']     = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER']     = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB']       = os.getenv('MYSQL_DB')

mysql = MySQL(app)

# ─── UPLOADS ───
UPLOAD_FOLDER    = os.path.join(
    os.path.dirname(__file__), 'static', 'uploads'
)
ALLOWED_IMAGES   = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_FICHIERS = {'pdf', 'csv', 'xlsx', 'xls', 'zip', 'json'}

app.config['UPLOAD_FOLDER']      = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

os.makedirs(os.path.join(UPLOAD_FOLDER, 'images'),   exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'fichiers'), exist_ok=True)

def allowed_image(f):
    return '.' in f and \
           f.rsplit('.', 1)[1].lower() in ALLOWED_IMAGES

def allowed_fichier(f):
    return '.' in f and \
           f.rsplit('.', 1)[1].lower() in ALLOWED_FICHIERS

def sauvegarder_fichier(fichier, sous_dossier):
    if fichier and fichier.filename != '':
        filename   = secure_filename(fichier.filename)
        nom_unique = f"{int(time.time())}_{filename}"
        chemin     = os.path.join(
            app.config['UPLOAD_FOLDER'],
            sous_dossier, nom_unique
        )
        fichier.save(chemin)
        return f"/static/uploads/{sous_dossier}/{nom_unique}"
    return None

def generer_slug(titre):
    slug = titre.lower()
    for a, b in [('é','e'),('è','e'),('ê','e'),('à','a'),
                 ('â','a'),('ô','o'),('î','i'),('ù','u'),
                 ('ç','c'),('û','u'),("'", '-'),("'", '-')]:
        slug = slug.replace(a, b)
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug).strip('-')
    return slug

# ─── DÉCORATEUR ADMIN ───
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Accès réservé.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/')
def index():
    try:
        cur = mysql.connection.cursor()

        # Dernière analyse
        cur.execute("""
            SELECT id, titre, slug, categorie, extrait,
                   temps_lecture, source, couleur,
                   date_publication, image_url
            FROM analyses
            WHERE actif = 1
            ORDER BY date_publication DESC
            LIMIT 1
        """)
        derniere_analyse = cur.fetchone()

        # Analyse à la une
        cur.execute("""
            SELECT id, titre, slug, categorie, extrait,
                   temps_lecture, source, couleur,
                   date_publication, image_url
            FROM analyses
            WHERE actif = 1 AND une = 1
            ORDER BY date_publication DESC
            LIMIT 1
        """)
        analyse_une = cur.fetchone()

        # Analyses récentes (hors une)
        cur.execute("""
            SELECT id, titre, slug, categorie, extrait,
                   temps_lecture, source, couleur,
                   date_publication, image_url
            FROM analyses
            WHERE actif = 1
            ORDER BY date_publication DESC
            LIMIT 3
        """)
        analyses_recentes = cur.fetchall()

        # Stats par thème
        cur.execute("""
            SELECT categorie, COUNT(*) 
            FROM analyses 
            WHERE actif = 1 
            GROUP BY categorie
        """)
        themes_raw = dict(cur.fetchall())

        themes = {
            'sante':        themes_raw.get('sante', 0),
            'education':    themes_raw.get('education', 0),
            'economie':     themes_raw.get('economie', 0),
            'gouvernance':  themes_raw.get('gouvernance', 0),
            'agriculture':  themes_raw.get('agriculture', 0),
            'environnement':themes_raw.get('environnement', 0),
        }

        # Total analyses
        cur.execute("SELECT COUNT(*) FROM analyses WHERE actif=1")
        nb_analyses = cur.fetchone()[0]

        cur.close()

    except Exception as e:
        print(f"Erreur index : {e}")
        derniere_analyse  = None
        analyse_une       = None
        analyses_recentes = []
        themes = {k:0 for k in ['sante','education','economie',
                                  'gouvernance','agriculture',
                                  'environnement']}
        nb_analyses = 0

    # Fact du jour — statique pour l'instant
    fact = {
        'chiffre': '41.5%',
        'texte'  : 'C\'est le taux de réussite national au BAC 2025 '
                'en Côte d\'Ivoire. Derrière cette moyenne, '
                '20 régions sur 33 sont sous ce seuil — '
                'et un écart de 28 points sépare Abidjan (52.7%) '
                'du Bafing (24.7%).',
        'source' : 'Source : Dataivoire — BAC 2025  ·  '
                'Données vérifiées  ·  Hors candidats libres'
    }

    stats = {'analyses': nb_analyses}

    return render_template('index.html',
        derniere_analyse  = derniere_analyse,
        analyse_une       = analyse_une,
        analyses_recentes = analyses_recentes,
        themes            = themes,
        stats             = stats,
        fact              = fact
    )

@app.route('/analyses')
def analyses():
    theme = request.args.get('theme', 'tous')

    try:
        cur = mysql.connection.cursor()

        if theme and theme != 'tous':
            cur.execute("""
                SELECT id, titre, slug, categorie, extrait,
                       temps_lecture, source, couleur,
                       date_publication, image_url
                FROM analyses
                WHERE actif = 1 AND categorie = %s
                ORDER BY date_publication DESC
            """, (theme,))
        else:
            cur.execute("""
                SELECT id, titre, slug, categorie, extrait,
                       temps_lecture, source, couleur,
                       date_publication, image_url
                FROM analyses
                WHERE actif = 1
                ORDER BY date_publication DESC
            """)

        analyses = cur.fetchall()

        # Comptage par thème
        cur.execute("""
            SELECT categorie, COUNT(*)
            FROM analyses
            WHERE actif = 1
            GROUP BY categorie
        """)
        themes_raw = dict(cur.fetchall())

        cur.execute(
            "SELECT COUNT(*) FROM analyses WHERE actif = 1"
        )
        total = cur.fetchone()[0]

        cur.close()

    except Exception as e:
        print(f"Erreur analyses : {e}")
        analyses   = []
        themes_raw = {}
        total      = 0

    themes = {
        'tous':         total,
        'sante':        themes_raw.get('sante', 0),
        'education':    themes_raw.get('education', 0),
        'economie':     themes_raw.get('economie', 0),
        'gouvernance':  themes_raw.get('gouvernance', 0),
        'agriculture':  themes_raw.get('agriculture', 0),
        'environnement':themes_raw.get('environnement', 0),
    }

    return render_template('analyses.html',
        analyses = analyses,
        themes   = themes,
        theme    = theme
    )

@app.route('/analyses/<slug>')
def analyse_detail(slug):
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, titre, slug, categorie, extrait,
                   contenu, temps_lecture, source, couleur,
                   date_publication, image_url,
                   fichier_url, fichier_nom
            FROM analyses
            WHERE slug = %s AND actif = 1
        """, (slug,))
        analyse = cur.fetchone()

        # 3 analyses similaires
        if analyse:
            cur.execute("""
                SELECT id, titre, slug, categorie,
                       extrait, temps_lecture,
                       date_publication, image_url
                FROM analyses
                WHERE actif = 1
                AND categorie = %s
                AND slug != %s
                ORDER BY date_publication DESC
                LIMIT 3
            """, (analyse[3], slug))
            similaires = cur.fetchall()
        else:
            similaires = []

        cur.close()

    except Exception as e:
        print(f"Erreur analyse detail : {e}")
        analyse    = None
        similaires = []

    if not analyse:
        return redirect(url_for('analyses'))

    return render_template('analyse_detail.html',
        analyse    = analyse,
        similaires = similaires
    )


@app.route('/donnees')
def donnees():
    categorie = request.args.get('categorie', 'toutes')

    try:
        cur = mysql.connection.cursor()

        if categorie and categorie != 'toutes':
            cur.execute("""
                SELECT id, titre, description, categorie,
                       source, source_url, fichier_url,
                       fichier_nom, fichier_type,
                       fichier_taille, annee, pays,
                       telechargements, date_ajout
                FROM donnees
                WHERE actif = 1 AND categorie = %s
                ORDER BY date_ajout DESC
            """, (categorie,))
        else:
            cur.execute("""
                SELECT id, titre, description, categorie,
                       source, source_url, fichier_url,
                       fichier_nom, fichier_type,
                       fichier_taille, annee, pays,
                       telechargements, date_ajout
                FROM donnees
                WHERE actif = 1
                ORDER BY date_ajout DESC
            """)

        donnees_list = cur.fetchall()

        # Comptage par catégorie
        cur.execute("""
            SELECT categorie, COUNT(*)
            FROM donnees
            WHERE actif = 1
            GROUP BY categorie
        """)
        cats_raw = dict(cur.fetchall())

        cur.execute(
            "SELECT COUNT(*) FROM donnees WHERE actif = 1"
        )
        total = cur.fetchone()[0]

        # Total téléchargements
        cur.execute(
            "SELECT SUM(telechargements) FROM donnees WHERE actif = 1"
        )
        total_dl = cur.fetchone()[0] or 0

        cur.close()

    except Exception as e:
        print(f"Erreur donnees : {e}")
        donnees_list = []
        cats_raw     = {}
        total        = 0
        total_dl     = 0

    categories = {
        'toutes':       total,
        'sante':        cats_raw.get('sante', 0),
        'education':    cats_raw.get('education', 0),
        'economie':     cats_raw.get('economie', 0),
        'gouvernance':  cats_raw.get('gouvernance', 0),
        'agriculture':  cats_raw.get('agriculture', 0),
        'environnement':cats_raw.get('environnement', 0),
    }

    return render_template('donnees.html',
        donnees    = donnees_list,
        categories = categories,
        categorie  = categorie,
        total      = total,
        total_dl   = total_dl
    )


@app.route('/donnees/telecharger/<int:id>')
def donnees_telecharger(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE donnees
            SET telechargements = telechargements + 1
            WHERE id = %s
        """, (id,))
        mysql.connection.commit()

        cur.execute(
            "SELECT fichier_url, fichier_nom FROM donnees WHERE id = %s",
            (id,)
        )
        d = cur.fetchone()
        cur.close()

        if d and d[0]:
            return redirect(d[0])
        else:
            flash('Fichier non disponible.', 'error')
            return redirect(url_for('donnees'))

    except Exception as e:
        print(f"Erreur téléchargement : {e}")
        return redirect(url_for('donnees'))
    

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/collaborer', methods=['GET', 'POST'])
def collaborer():
    if request.method == 'POST':
        nom          = request.form.get('nom', '').strip()
        organisation = request.form.get('organisation', '').strip()
        email        = request.form.get('email', '').strip()
        type_collab  = request.form.get('type_collab', '').strip()
        message      = request.form.get('message', '').strip()

        if not nom or not email or not message:
            flash('Veuillez remplir tous les champs obligatoires.',
                  'error')
            return redirect(url_for('collaborer'))

        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO contacts
                    (nom, email, service, message)
                VALUES (%s, %s, %s, %s)
            """, (
                f"{nom} ({organisation})" if organisation else nom,
                email,
                type_collab,
                message
            ))
            mysql.connection.commit()
            cur.close()
            flash('Message envoyé. Nous vous répondons sous 48h.',
                  'success')
        except Exception as e:
            print(f"Erreur collaborer : {e}")
            flash('Erreur. Veuillez réessayer.', 'error')

        return redirect(url_for('collaborer'))

    return render_template('collaborer.html')


# ─── ERREURS ───
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500



# ─── UPLOADS ───
UPLOAD_FOLDER    = os.path.join(
    os.path.dirname(__file__), 'static', 'uploads'
)
ALLOWED_IMAGES   = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_FICHIERS = {'pdf', 'csv', 'xlsx', 'xls', 'zip', 'json'}

app.config['UPLOAD_FOLDER']      = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

os.makedirs(os.path.join(UPLOAD_FOLDER, 'images'),   exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'fichiers'), exist_ok=True)

def allowed_image(f):
    return '.' in f and \
           f.rsplit('.', 1)[1].lower() in ALLOWED_IMAGES

def allowed_fichier(f):
    return '.' in f and \
           f.rsplit('.', 1)[1].lower() in ALLOWED_FICHIERS

def sauvegarder_fichier(fichier, sous_dossier):
    if fichier and fichier.filename != '':
        filename   = secure_filename(fichier.filename)
        nom_unique = f"{int(time.time())}_{filename}"
        chemin     = os.path.join(
            app.config['UPLOAD_FOLDER'],
            sous_dossier, nom_unique
        )
        fichier.save(chemin)
        return f"/static/uploads/{sous_dossier}/{nom_unique}"
    return None

def generer_slug(titre):
    slug = titre.lower()
    for a, b in [('é','e'),('è','e'),('ê','e'),('à','a'),
                 ('â','a'),('ô','o'),('î','i'),('ù','u'),
                 ('ç','c'),('û','u'),("'", '-'),("'", '-')]:
        slug = slug.replace(a, b)
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug).strip('-')
    return slug

# ─── DÉCORATEUR ADMIN ───
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Accès réservé.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ════════════════════════════════════
# ADMIN — AUTH
# ════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin_logged_in' in session:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        try:
            cur = mysql.connection.cursor()
            cur.execute(
                "SELECT * FROM admins WHERE username = %s",
                (username,)
            )
            admin = cur.fetchone()
            cur.close()
            if admin and check_password_hash(admin[2], password):
                session['admin_logged_in'] = True
                session['admin_username']  = admin[1]
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Identifiants incorrects.', 'error')
        except Exception as e:
            print(f"Erreur login : {e}")
            flash('Erreur de connexion.', 'error')

    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


# ════════════════════════════════════
# ADMIN — DASHBOARD
# ════════════════════════════════════

@app.route('/admin')
@login_required
def admin_dashboard():
    try:
        cur = mysql.connection.cursor()

        cur.execute(
            "SELECT COUNT(*) FROM analyses WHERE actif=1"
        )
        nb_analyses = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM analyses WHERE actif=0"
        )
        nb_brouillons = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM donnees WHERE actif=1"
        )
        nb_donnees = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM contacts WHERE lu=0"
        )
        nb_messages = cur.fetchone()[0]

        cur.execute("""
            SELECT id, titre, categorie, actif,
                   date_publication
            FROM analyses
            ORDER BY date_publication DESC
            LIMIT 5
        """)
        recentes = cur.fetchall()

        cur.execute("""
            SELECT id, nom, email, service,
                   LEFT(message,60), date_envoi, lu
            FROM contacts
            ORDER BY date_envoi DESC
            LIMIT 5
        """)
        derniers_messages = cur.fetchall()

        cur.close()

    except Exception as e:
        print(f"Erreur dashboard : {e}")
        nb_analyses = nb_brouillons = nb_donnees = nb_messages = 0
        recentes = derniers_messages = []

    return render_template('admin/dashboard.html',
        nb_analyses       = nb_analyses,
        nb_brouillons     = nb_brouillons,
        nb_donnees        = nb_donnees,
        nb_messages       = nb_messages,
        recentes          = recentes,
        derniers_messages = derniers_messages
    )


# ════════════════════════════════════
# ADMIN — ANALYSES
# ════════════════════════════════════

@app.route('/admin/analyses')
@login_required
def admin_analyses():
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, titre, categorie, actif,
                   une, date_publication, date_creation
            FROM analyses
            ORDER BY date_creation DESC
        """)
        analyses = cur.fetchall()
        cur.close()
    except Exception as e:
        print(f"Erreur admin analyses : {e}")
        analyses = []
    return render_template('admin/analyses.html',
                           analyses=analyses)


@app.route('/admin/analyses/ajouter', methods=['GET', 'POST'])
@login_required
def admin_analyse_ajouter():
    if request.method == 'POST':
        titre    = request.form.get('titre', '').strip()
        categorie= request.form.get('categorie', '').strip()
        extrait  = request.form.get('extrait', '').strip()
        contenu  = request.form.get('contenu', '').strip()
        temps    = request.form.get('temps_lecture', '5 min')
        source   = request.form.get('source', '').strip()
        couleur  = request.form.get('couleur', 'green')
        actif    = 1 if request.form.get('actif') else 0
        une      = 1 if request.form.get('une') else 0

        if not titre or not contenu:
            flash('Titre et contenu obligatoires.', 'error')
            return redirect(url_for('admin_analyse_ajouter'))

        slug = generer_slug(titre)

        image_url = None
        if 'image' in request.files:
            img = request.files['image']
            if img and allowed_image(img.filename):
                image_url = sauvegarder_fichier(img, 'images')

        fichier_url = fichier_nom = None
        if 'fichier' in request.files:
            fic = request.files['fichier']
            if fic and allowed_fichier(fic.filename):
                fichier_url = sauvegarder_fichier(fic, 'fichiers')
                fichier_nom = fic.filename

        try:
            cur = mysql.connection.cursor()

            if actif:
                cur.execute("""
                    INSERT INTO analyses (
                        titre, slug, categorie, extrait,
                        contenu, temps_lecture, source,
                        couleur, actif, une,
                        image_url, fichier_url, fichier_nom,
                        date_publication
                    ) VALUES (
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,
                        NOW()
                    )
                """, (titre, slug, categorie, extrait,
                    contenu, temps, source, couleur,
                    actif, une, image_url, fichier_url,
                    fichier_nom))
            else:
                cur.execute("""
                    INSERT INTO analyses (
                        titre, slug, categorie, extrait,
                        contenu, temps_lecture, source,
                        couleur, actif, une,
                        image_url, fichier_url, fichier_nom
                    ) VALUES (
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s
                    )
                """, (titre, slug, categorie, extrait,
                    contenu, temps, source, couleur,
                    actif, une, image_url, fichier_url,
                    fichier_nom))

            mysql.connection.commit()
            cur.close()
            flash('Analyse ajoutée avec succès.', 'success')
            return redirect(url_for('admin_analyses'))

        except Exception as e:
            print(f"Erreur ajout analyse : {e}")
            flash('Erreur — le titre existe peut-être déjà.', 'error')
    return render_template('admin/analyse_form.html', analyse=analyses, action='ajouter')


@app.route('/admin/analyses/modifier/<int:id>',
           methods=['GET', 'POST'])
@login_required
def admin_analyse_modifier(id):
    if request.method == 'POST':
        titre    = request.form.get('titre', '').strip()
        categorie= request.form.get('categorie', '').strip()
        extrait  = request.form.get('extrait', '').strip()
        contenu  = request.form.get('contenu', '').strip()
        temps    = request.form.get('temps_lecture', '5 min')
        source   = request.form.get('source', '').strip()
        couleur  = request.form.get('couleur', 'green')
        actif    = 1 if request.form.get('actif') else 0
        une      = 1 if request.form.get('une') else 0

        image_url = fichier_url = fichier_nom = None
        if 'image' in request.files:
            img = request.files['image']
            if img and img.filename != '' and \
               allowed_image(img.filename):
                image_url = sauvegarder_fichier(img, 'images')

        if 'fichier' in request.files:
            fic = request.files['fichier']
            if fic and fic.filename != '' and \
               allowed_fichier(fic.filename):
                fichier_url = sauvegarder_fichier(fic, 'fichiers')
                fichier_nom = fic.filename

        try:
            cur = mysql.connection.cursor()
            if image_url and fichier_url:
                cur.execute("""
                    UPDATE analyses SET
                        titre=%s, categorie=%s, extrait=%s,
                        contenu=%s, temps_lecture=%s,
                        source=%s, couleur=%s, actif=%s,
                        une=%s, image_url=%s,
                        fichier_url=%s, fichier_nom=%s,
                        date_publication = CASE
                            WHEN %s=1 AND date_publication IS NULL
                            THEN NOW()
                            ELSE date_publication END
                    WHERE id=%s
                """, (titre, categorie, extrait, contenu,
                      temps, source, couleur, actif, une,
                      image_url, fichier_url, fichier_nom,
                      actif, id))
            elif image_url:
                cur.execute("""
                    UPDATE analyses SET
                        titre=%s, categorie=%s, extrait=%s,
                        contenu=%s, temps_lecture=%s,
                        source=%s, couleur=%s, actif=%s,
                        une=%s, image_url=%s,
                        date_publication = CASE
                            WHEN %s=1 AND date_publication IS NULL
                            THEN NOW()
                            ELSE date_publication END
                    WHERE id=%s
                """, (titre, categorie, extrait, contenu,
                      temps, source, couleur, actif, une,
                      image_url, actif, id))
            elif fichier_url:
                cur.execute("""
                    UPDATE analyses SET
                        titre=%s, categorie=%s, extrait=%s,
                        contenu=%s, temps_lecture=%s,
                        source=%s, couleur=%s, actif=%s,
                        une=%s, fichier_url=%s, fichier_nom=%s,
                        date_publication = CASE
                            WHEN %s=1 AND date_publication IS NULL
                            THEN NOW()
                            ELSE date_publication END
                    WHERE id=%s
                """, (titre, categorie, extrait, contenu,
                      temps, source, couleur, actif, une,
                      fichier_url, fichier_nom, actif, id))
            else:
                cur.execute("""
                    UPDATE analyses SET
                        titre=%s, categorie=%s, extrait=%s,
                        contenu=%s, temps_lecture=%s,
                        source=%s, couleur=%s, actif=%s,
                        une=%s,
                        date_publication = CASE
                            WHEN %s=1 AND date_publication IS NULL
                            THEN NOW()
                            ELSE date_publication END
                    WHERE id=%s
                """, (titre, categorie, extrait, contenu,
                      temps, source, couleur, actif, une,
                      actif, id))
            mysql.connection.commit()
            cur.close()
            flash('Analyse modifiée.', 'success')
            return redirect(url_for('admin_analyses'))
        except Exception as e:
            print(f"Erreur modification : {e}")
            flash('Erreur lors de la modification.', 'error')
            return redirect(
                url_for('admin_analyse_modifier', id=id)
            )

    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT * FROM analyses WHERE id=%s", (id,)
        )
        analyse = cur.fetchone()
        cur.close()
    except Exception as e:
        print(f"Erreur chargement : {e}")
        analyse = None

    return render_template('admin/analyse_form.html', analyse=analyse, action='modifier')


@app.route('/admin/analyses/supprimer/<int:id>',
           methods=['POST'])
@login_required
def admin_analyse_supprimer(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "DELETE FROM analyses WHERE id=%s", (id,)
        )
        mysql.connection.commit()
        cur.close()
        flash('Analyse supprimée.', 'success')
    except Exception as e:
        print(f"Erreur suppression : {e}")
        flash('Erreur lors de la suppression.', 'error')
    return redirect(url_for('admin_analyses'))


@app.route('/admin/analyses/toggle/<int:id>',
           methods=['POST'])
@login_required
def admin_analyse_toggle(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE analyses SET
                actif = NOT actif,
                date_publication = CASE
                    WHEN NOT actif = 1
                    AND date_publication IS NULL
                    THEN NOW()
                    ELSE date_publication END
            WHERE id=%s
        """, (id,))
        mysql.connection.commit()
        cur.close()
    except Exception as e:
        print(f"Erreur toggle : {e}")
    return redirect(url_for('admin_analyses'))


# ════════════════════════════════════
# ADMIN — DONNÉES
# ════════════════════════════════════

@app.route('/admin/donnees')
@login_required
def admin_donnees():
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, titre, categorie, source,
                   fichier_type, actif,
                   telechargements, date_ajout
            FROM donnees
            ORDER BY date_ajout DESC
        """)
        donnees = cur.fetchall()
        cur.close()
    except Exception as e:
        print(f"Erreur admin donnees : {e}")
        donnees = []
    return render_template('admin/donnees.html',
                           donnees=donnees)


@app.route('/admin/donnees/ajouter', methods=['GET', 'POST'])
@login_required
def admin_donnee_ajouter():
    if request.method == 'POST':
        titre         = request.form.get('titre', '').strip()
        description   = request.form.get('description', '').strip()
        categorie     = request.form.get('categorie', '').strip()
        source        = request.form.get('source', '').strip()
        source_url    = request.form.get('source_url', '').strip()
        fichier_type  = request.form.get('fichier_type', '').strip()
        fichier_taille= request.form.get('fichier_taille', '').strip()
        annee         = request.form.get('annee', '').strip()
        pays          = request.form.get('pays', 'Côte d\'Ivoire')
        actif         = 1 if request.form.get('actif') else 0

        fichier_url = fichier_nom = None
        if 'fichier' in request.files:
            fic = request.files['fichier']
            if fic and allowed_fichier(fic.filename):
                fichier_url = sauvegarder_fichier(
                    fic, 'fichiers'
                )
                fichier_nom = fic.filename
                ext = fic.filename.rsplit('.', 1)[-1].upper()
                if not fichier_type:
                    fichier_type = ext

        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO donnees (
                    titre, description, categorie,
                    source, source_url,
                    fichier_url, fichier_nom,
                    fichier_type, fichier_taille,
                    annee, pays, actif
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                )
            """, (titre, description, categorie,
                  source, source_url,
                  fichier_url, fichier_nom,
                  fichier_type, fichier_taille,
                  annee, pays, actif))
            mysql.connection.commit()
            cur.close()
            flash('Jeu de données ajouté.', 'success')
            return redirect(url_for('admin_donnees'))
        except Exception as e:
            print(f"Erreur ajout donnee : {e}")
            flash('Erreur lors de l\'ajout.', 'error')

    return render_template('admin/donnee_form.html',
                           donnee=None, action='ajouter')


@app.route('/admin/donnees/supprimer/<int:id>',
           methods=['POST'])
@login_required
def admin_donnee_supprimer(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM donnees WHERE id=%s", (id,))
        mysql.connection.commit()
        cur.close()
        flash('Jeu de données supprimé.', 'success')
    except Exception as e:
        print(f"Erreur suppression donnee : {e}")
        flash('Erreur.', 'error')
    return redirect(url_for('admin_donnees'))


# ════════════════════════════════════
# ADMIN — MESSAGES
# ════════════════════════════════════

@app.route('/admin/messages')
@login_required
def admin_messages():
    filtre = request.args.get('filtre', 'tous')
    try:
        cur = mysql.connection.cursor()
        if filtre == 'non_lus':
            cur.execute("""
                SELECT id, nom, email, service,
                       message, date_envoi, lu
                FROM contacts WHERE lu=0
                ORDER BY date_envoi DESC
            """)
        else:
            cur.execute("""
                SELECT id, nom, email, service,
                       message, date_envoi, lu
                FROM contacts
                ORDER BY date_envoi DESC
            """)
        messages = cur.fetchall()
        cur.close()
    except Exception as e:
        print(f"Erreur messages : {e}")
        messages = []
    return render_template('admin/messages.html',
                           messages=messages, filtre=filtre)


@app.route('/admin/messages/<int:id>/lu', methods=['POST'])
@login_required
def admin_marquer_lu(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "UPDATE contacts SET lu=1 WHERE id=%s", (id,)
        )
        mysql.connection.commit()
        cur.close()
    except Exception as e:
        print(f"Erreur lu : {e}")
    return redirect(url_for('admin_messages'))


@app.route('/admin/messages/<int:id>/supprimer',
           methods=['POST'])
@login_required
def admin_message_supprimer(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "DELETE FROM contacts WHERE id=%s", (id,)
        )
        mysql.connection.commit()
        cur.close()
        flash('Message supprimé.', 'success')
    except Exception as e:
        print(f"Erreur suppression message : {e}")
    return redirect(url_for('admin_messages'))


if __name__ == '__main__':
    app.run(debug=True)