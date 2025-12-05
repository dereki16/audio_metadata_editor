"""
Genre Manager - Manages genre list for dropdown
"""


class GenreManager:
    """Provides genre list for audio metadata"""
    
    GENRES = [
        "Acid Rock", "Acid Techno", "Acoustic", "Afrobeat", "Alternative", 
        "Alternative Dance", "Alternative Metal", "Alternative R&B", "Alternative Rock", 
        "Ambient", "Americana", "Anime", "Arena Rock", "Art Pop", "Art Rock", 
        "Atmospheric", "Bachata", "Balada", "Baroque Pop", "Bass House", "Bass Music", 
        "Beat Music", "Bedroom Pop", "Big Beat", "Big Room House", "Blackgaze", 
        "Bluegrass", "Blues", "Blues Rock", "Bossa Nova", "Breakbeat", "Britpop", 
        "British Invasion", "Brostep", "Canción", "Cantautor", "Chamber Pop", 
        "Chillhop", "Chillout", "Chillwave", "Classic Rock", "Classical", "Country", 
        "Country Pop", "Cumbia", "Dance", "Dance-Pop", "Dancehall", "Deep House", 
        "Disco", "Downtempo", "Dream Pop", "Drone", "Dub", "Dubstep", "EDM", 
        "Electro", "Electronica", "Electronic", "Emo", "Emo Pop", "Emo Rock", 
        "Experimental", "Flamenco", "Folk", "Folk Rock", "Folktronica", "Freestyle", 
        "Funk", "Future Bass", "Garage Rock", "Glam Punk", "Glitch", "Gospel", 
        "Gothic", "Grunge", "Hard Rock", "Hardcore", "Hardstyle", "Hip-Hop", 
        "House", "Indie", "Indie Folk", "Indie Pop", "Indie Rock", "Indietronica", 
        "Industrial", "Jangle Pop", "Jazz", "Jazz Fusion", "Jazz/Chill Lofi", 
        "K-Pop", "Latin", "Latin Pop", "Latin Rock", "Lo-Fi", "Lo-Fi Hip Hop", 
        "Mariachi", "Math Rock", "Metal", "Microhouse", "Minimal", "Música Popular Brasileira", 
        "New Age", "New Wave", "Noise Rock", "Nu-Disco", "Opera", "Orchestral Pop", 
        "Pop", "Pop Metal", "Pop Rap", "Pop Rock", "Pop-Punk", "Post-Rock", 
        "Post-Punk", "Power Pop", "Progressive", "Progressive House", "Progressive Rock", 
        "Psychedelic", "Psychedelic Pop", "Punk", "Punk Rock", "R&B", "Ranchera", 
        "Rap", "Reggae", "Reggaeton", "Rock", "Rock & Roll", "Rock En Español", 
        "Salsa", "Shoegaze", "Ska", "Soft Rock", "Soul", "Soundtrack", "Spanish Pop", 
        "Synthpop", "Synthwave", "Techno", "Teen Pop", "Trance", "Trap", "Trap Music", 
        "Tropical", "Tropical House", "Vallenato", "Vaporwave", "Vocaloid", "World"
    ]
    
    @staticmethod
    def get_genres():
        """Get sorted list of genres"""
        return [""] + sorted(GenreManager.GENRES)
    
    @staticmethod
    def populate_combobox(combobox):
        """Populate a QComboBox with genres"""
        combobox.clear()
        combobox.addItems(GenreManager.get_genres())