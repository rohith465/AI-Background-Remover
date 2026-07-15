from rembg import remove
from PIL import Image
import os

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    flash,
    session,
    send_from_directory
)

from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

app.secret_key = "your_secret_key"

# ------------------------------
# Folder Configuration
# ------------------------------
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

# Create folders if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ------------------------------
# MySQL Configuration
# ------------------------------
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "flaskuser"
app.config["MYSQL_PASSWORD"] = "mypassword123"
app.config["MYSQL_DB"] = "ai_background_remover"

mysql = MySQL(app)

# ------------------------------
# Home
# ------------------------------
@app.route("/")
def home():
    return render_template("index.html")


# ------------------------------
# Register
# ------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        fullname = request.form["fullname"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect("/register")

        cursor = mysql.connection.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=%s",
            (email,)
        )

        user = cursor.fetchone()

        if user:
            cursor.close()
            flash("Email already registered!")
            return redirect("/register")

        hashed_password = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO users(fullname,email,password)
            VALUES(%s,%s,%s)
            """,
            (fullname, email, hashed_password)
        )

        mysql.connection.commit()
        cursor.close()

        flash("Registration Successful!")
        return redirect("/login")

    return render_template("register.html")


# ------------------------------
# Login
# ------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        cursor = mysql.connection.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=%s",
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()

        if user:

            if check_password_hash(user[3], password):

                session["user_id"] = user[0]
                session["fullname"] = user[1]

                flash("Login Successful!")

                return redirect("/dashboard")

            else:
                flash("Incorrect Password")

        else:
            flash("Email Not Found")

    return render_template("login.html")


# ------------------------------
# Dashboard
# ------------------------------
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    filename = None
    png_filename = None
    jpg_filename = None

    # Load previous uploaded images
    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT id,
               original_image,
               output_png,
               output_jpg,
               uploaded_at
        FROM images
        WHERE user_id=%s
        ORDER BY uploaded_at DESC
        """,
        (session["user_id"],)
    )

    images = cursor.fetchall()
    cursor.close()

    # Upload new image
    if request.method == "POST":

        if "image" not in request.files:
            flash("Please select an image!")
            return redirect("/dashboard")

        image = request.files["image"]

        if image.filename == "":
            flash("Please choose an image!")
            return redirect("/dashboard")

        # Save uploaded image
        filename = secure_filename(image.filename)

        upload_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        image.save(upload_path)

        # Open uploaded image
        input_image = Image.open(upload_path)

        # Remove background
        output = remove(input_image)

        image_name = os.path.splitext(filename)[0]

        # -------------------------
        # Save PNG
        # -------------------------
        png_filename = f"removed_{image_name}.png"

        png_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            png_filename
        )

        output.save(png_path, "PNG")

        # -------------------------
        # Save JPG
        # -------------------------
        jpg_filename = f"removed_{image_name}.jpg"

        jpg_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            jpg_filename
        )

        rgb_output = Image.new(
            "RGB",
            output.size,
            (255, 255, 255)
        )

        rgb_output.paste(
            output,
            mask=output.getchannel("A")
        )

        rgb_output.save(
            jpg_path,
            "JPEG",
            quality=95
        )

        # -------------------------
        # Save details in database
        # -------------------------
        cursor = mysql.connection.cursor()

        cursor.execute(
            """
            INSERT INTO images
            (user_id, original_image, output_png, output_jpg)
            VALUES (%s, %s, %s, %s)
            """,
            (
                session["user_id"],
                filename,
                png_filename,
                jpg_filename
            )
        )

        mysql.connection.commit()
        cursor.close()

        # Reload upload history
        cursor = mysql.connection.cursor()

        cursor.execute(
            """
            SELECT id,
                   original_image,
                   output_png,
                   output_jpg,
                   uploaded_at
            FROM images
            WHERE user_id=%s
            ORDER BY uploaded_at DESC
            """,
            (session["user_id"],)
        )

        images = cursor.fetchall()
        cursor.close()

        flash("Background Removed Successfully!")

    return render_template(
        "dashboard.html",
        fullname=session["fullname"],
        filename=filename,
        png_filename=png_filename,
        jpg_filename=jpg_filename,
        images=images
    )



    
# ------------------------------
# Logout
# ------------------------------
@app.route("/logout")
def logout():

    session.clear()

    flash("Logged out successfully!")

    return redirect("/login")


# ------------------------------
# Uploaded Images
# ------------------------------
@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# ------------------------------
# Output Images
# ------------------------------
@app.route("/output/<filename>")
def output_file(filename):

    return send_from_directory(
        app.config["OUTPUT_FOLDER"],
        filename
    )


# ------------------------------
# Run Application
# ------------------------------
# ------------------------------
# Delete Image
# ------------------------------
@app.route("/delete/<int:image_id>")
def delete_image(image_id):

    if "user_id" not in session:
        return redirect("/login")

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT original_image,
               output_png,
               output_jpg
        FROM images
        WHERE id=%s AND user_id=%s
        """,
        (image_id, session["user_id"])
    )

    image = cursor.fetchone()

    if image:

        original_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            image[0]
        )

        png_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            image[1]
        )

        jpg_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            image[2]
        )

        if os.path.exists(original_path):
            os.remove(original_path)

        if os.path.exists(png_path):
            os.remove(png_path)

        if os.path.exists(jpg_path):
            os.remove(jpg_path)

        cursor.execute(
            "DELETE FROM images WHERE id=%s",
            (image_id,)
        )

        mysql.connection.commit()

    cursor.close()

    flash("Image deleted successfully!")

    return redirect("/dashboard")




if __name__ == "__main__":
    app.run(debug=True)