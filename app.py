import datetime
import hashlib
from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from jaeger_client import Config
from flask_opentracing import FlaskTracing


from ddtrace import tracer



from ddtrace import config, patch_all
from ddtrace.runtime import RuntimeMetrics

# from opentelemetry.exporter import jaeger
# from opentelemetry import trace
# from opentelemetry.exporter.jaeger.thrift import JaegerExporter
# from opentelemetry.sdk.resources import SERVICE_NAME, Resource
# from opentelemetry.sdk.trace import TracerProvider
# from opentelemetry.sdk.trace.export import BatchSpanProcessor

# resource = Resource(attributes={
#    SERVICE_NAME: "app"
# })

# jaeger_exporter = JaegerExporter(
#    agent_host_name="localhost",
#    agent_port=6831,
#    collector_endpoint='http://localhost:16686/api/traces?format=jaeger.thrift',
# )



# provider = TracerProvider(resource=resource)
# processor = BatchSpanProcessor(jaeger_exporter)
# provider.add_span_processor(processor)
# trace.set_tracer_provider(provider)

RuntimeMetrics.enable()
config.flask['service_name'] = "app"
config.env = "dev"      # the environment the application is in
config.service = "app"  # name of your application
config.version = "0.1"  # version of your application
patch_all()

# # Network sockets
# tracer.configure(
#     https=False,
#     hostname="Niddhi",
#     port=8125,

# )




app = Flask(__name__)
config = Config(
    config={
        'sampler':
        {'type': 'const',
         'param': 1},
        'logging': True,
        'reporter_batch_size': 1,}, 
        service_name="notebook-service")
jaeger_tracer = config.initialize_tracer()
tracing = FlaskTracing(jaeger_tracer, True, app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

db = SQLAlchemy(app)

global auth
auth = [False]


class Notebook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), default="My Notebook")
    password = db.Column(db.String(100), default=None)
    last_modified = db.Column(db.DateTime, default=datetime.datetime.today())


class Notes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(25), default="New Note")
    content = db.Column(db.Text, default=" ")
    notes_notebook = db.Column(db.Integer, nullable=False)
    last_modified = db.Column(db.DateTime, default=datetime.datetime.today())
    font = db.Column(db.String(25))
    color = db.Column(db.String(6))


class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(25), default="New Section")
    content = db.Column(db.Text, default=" ")
    note_id = db.Column(db.Integer, nullable=False)


@app.route("/")
def redirect_to_home():
    return redirect(url_for("home"))


@app.route("/home", methods=["GET", "POST"])
@tracer.wrap("flask.request", service="flask", resource="GET /home", span_type="web")
def home():
    all_notebooks = Notebook.query.all()

    length = len(all_notebooks)
    i = 0

    while i < length:
        auth.append(False)
        i += 1

    for i in all_notebooks:
        auth.append(False)

    if not all_notebooks:
        notebook_available = False
    else:
        notebook_available = True

    return render_template("index.html", notebooks=all_notebooks, notebook_available=notebook_available)


@app.route("/notebook/create", methods=["GET", "POST"])
def create_notebook():
    if request.method == "POST":
        if request.form["name"] and not request.form["name"].isspace():
            if request.form["password"] and not request.form["password"].isspace():
                db.session.add(Notebook(name=request.form["name"],
                                        password=hashlib.sha256(request.form["password"].encode('utf-8')).hexdigest()))
            else:
                db.session.add(Notebook(name=request.form["name"]))
            db.session.commit()
            return redirect("/home")
        else:
            return render_template("create_notebook.html", message="Name cannot be blank")
    else:
        return render_template("create_notebook.html")


@app.route("/notebooks/<int:notebook_id>/delete", methods=["GET", "POST"])
def delete_notebook(notebook_id):
    if request.method == "POST":
        if Notebook.query.get(notebook_id).password is not None:
            if hashlib.sha256(request.form["password"].encode('utf-8')).hexdigest() == Notebook.query.get(
                    notebook_id).password:
                Notebook.query.filter_by(id=notebook_id).delete()
                Notes.query.filter_by(notes_notebook=notebook_id).delete()
                db.session.commit()
                return redirect("/home")
            else:
                return render_template("delete_notebook.html", name=Notebook.query.get(notebook_id).name,
                                       id=notebook_id, password=True,
                                       message="The Password is Incorrect")
        else:
            Notebook.query.filter_by(id=notebook_id).delete()
            Notes.query.filter_by(notes_notebook=notebook_id).delete()
            db.session.commit()
            return redirect("/home")
    else:
        if Notebook.query.get(notebook_id).password is None:
            password = False
        else:
            password = True
        return render_template("delete_notebook.html", name=Notebook.query.get(notebook_id).name, id=notebook_id,
                               password=password)


@app.route("/notebooks/<int:notebook_id>/note/<int:note_id>/delete", methods=["GET", "POST"])
def delete_note(notebook_id, note_id):
    if request.method == "POST":
        Notes.query.filter_by(id=note_id).delete()
        Section.query.filter_by(note_id=note_id).delete()
        db.session.commit()
        return redirect("/notebooks/" + str(notebook_id))
    else:
        return render_template("delete_note.html", notebook=Notebook.query.get(notebook_id).id,
                               note=Notes.query.get(note_id).id)


@app.route("/notebooks/<int:notebook_id>", methods=["GET", "POST", "DELETE"])
def open_notebook(notebook_id):
    if Notebook.query.get(notebook_id).password is None:
        return render_template("open.html", notes=Notes.query.filter(Notes.notes_notebook == notebook_id),
                               notebook=Notebook.query.get(notebook_id), open=False)
    else:
        if auth[notebook_id]:
            return render_template("open.html", notes=Notes.query.filter(Notes.notes_notebook == notebook_id),
                                   notebook=Notebook.query.get(notebook_id), open=False)
        else:
            return redirect("/notebooks/" + str(notebook_id) + "/login")


@app.route("/notebooks/<int:notebook_id>/login", methods=["GET", "POST"])
def login_notebook(notebook_id):
    if request.method == "POST":
        password = hashlib.sha256(request.form["password"].encode('utf-8')).hexdigest()
        if password == Notebook.query.get(notebook_id).password:
            auth[notebook_id] = True
            return redirect("/notebooks/" + str(notebook_id))
        else:
            return render_template("notebook_login.html", notebook=Notebook.query.get(notebook_id),
                                   message="The password is "
                                           "incorrect")
    else:
        return render_template("notebook_login.html", notebook=Notebook.query.get(notebook_id))


@app.route("/notebooks/<int:notebook_id>/note/create", methods=["GET", "POST"])
def create_note(notebook_id):
    if request.method == "POST":
        if request.form["name"] and not request.form["name"].isspace():
            db.session.add(
                Notes(name=request.form["name"], content=request.form["content"], notes_notebook=notebook_id))
            db.session.commit()
            return redirect("/notebooks/" + str(notebook_id))
        else:
            return render_template("create_note.html", message="Name cannot be blank", id=notebook_id)
    else:
        return render_template("create_note.html", id=notebook_id)


@app.route("/notebooks/<int:notebook_id>/note/<int:note_id>", methods=["GET", "POST"])
def open_note(notebook_id, note_id):
    if request.method == "POST":
        Notes.query.get(note_id).name = request.form["title"]
        Notes.query.get(note_id).content = request.form["content"]

        Notes.query.get(note_id).name = request.form["title"]
        Notes.query.get(note_id).content = request.form["content"]

        if request.form["font"] and not request.form["font"].isspace():
            Notes.query.get(note_id).font = request.form["font"]
        if request.form["color"] and not request.form["color"].isspace():
            Notes.query.get(note_id).color = request.form["color"]

        for section in Section.query.filter_by(note_id=note_id):
            section.name = request.form[str(section.id) + "-section-title"]
            section.content = request.form[str(section.id) + "-section-content"]

        db.session.commit()
        return render_template("open.html", notes=Notes.query.filter(Notes.notes_notebook == notebook_id),
                               notebook=Notebook.query.get(notebook_id), open=True, opened=Notes.query.get(note_id),
                               sections=Section.query.filter_by(note_id=note_id))

    return render_template("open.html", notes=Notes.query.filter(Notes.notes_notebook == notebook_id),
                           notebook=Notebook.query.get(notebook_id), open=True, opened=Notes.query.get(note_id),
                           sections=Section.query.filter_by(note_id=note_id))


@app.route("/notebooks/<int:notebook_id>/edit", methods=["GET", "POST"])
def edit_notebook(notebook_id):
    if request.method == "POST":
        if request.form["name"] and not request.form["name"].isspace():
            Notebook.query.get(notebook_id).name = request.form["name"]
            db.session.commit()
            return open_notebook(notebook_id)
        else:
            return render_template("edit_notebook.html", notebook=Notebook.query.get(notebook_id),
                                   message="Name cannot be Blank")

    return render_template("edit_notebook.html", notebook=Notebook.query.get(notebook_id))


@app.route("/notebook/<int:notebook_id>/note/<int:note_id>/section/create", methods=["GET", "POST"])
def create_section(notebook_id, note_id):
    if request.method == "POST":
        db.session.add(Section(name=request.form["name"], note_id=note_id))
        db.session.commit()
        return render_template("open.html", notes=Notes.query.filter(Notes.notes_notebook == notebook_id),
                               notebook=Notebook.query.get(notebook_id), open=True, opened=Notes.query.get(note_id),
                               sections=Section.query.filter_by(note_id=note_id))

    return render_template("create_section.html", notebook=notebook_id, note=note_id)


@app.route("/notebook/<int:notebook_id>/note/<int:note_id>/section/<int:section_id>/delete", methods=["GET", "POST"])
def delete_section(notebook_id, note_id, section_id):
    if request.method == "POST":
        Section.query.filter_by(id=section_id).delete()
        db.session.commit()
        return render_template("open.html", notes=Notes.query.filter(Notes.notes_notebook == notebook_id),
                               notebook=Notebook.query.get(notebook_id), open=False)

    return render_template("delete_section.html", notebook=notebook_id, note=note_id, section=Section.query.get(section_id))


if __name__ == "__main__":
   app.run(host='127.0.0.1',port=8000, debug=True)
