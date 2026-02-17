from app import create_app

gpm_app = create_app()

if __name__ == '__main__':
    gpm_app.run(debug=True,port=5001)