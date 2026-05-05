import random
import pygame


class MusicManager:
    """Manages music playback with shuffled track ordering.
    
    Shuffles the music tracks once at initialization, maintaining the same
    order throughout the game session. Provides methods to play and advance
    through the shuffled playlist.
    """
    
    MUSIC_END_EVENT = pygame.USEREVENT + 1
    
    def __init__(self, music_tracks):
        """Initialize the music manager with a shuffled playlist.
        
        Args:
            music_tracks: List of music file paths to shuffle and manage
        """
        self.original_tracks = music_tracks
        self.shuffled_tracks = list(music_tracks)  # Create a copy
        random.shuffle(self.shuffled_tracks)  # Shuffle once at init
        
        self.music_enabled = False
        self.current_index = 0
    
    def initialize_mixer(self):
        """Initialize pygame mixer for music playback.
        
        Returns:
            bool: True if mixer initialized successfully, False otherwise
        """
        if not self.shuffled_tracks:
            return False
        
        try:
            pygame.mixer.init()
            pygame.mixer.music.set_endevent(self.MUSIC_END_EVENT)
            self.music_enabled = True
            return True
        except pygame.error:
            self.music_enabled = False
            return False
    
    def start_playback(self):
        """Start playing the shuffled playlist from the beginning."""
        if not self.music_enabled or not self.shuffled_tracks:
            return
        
        self.current_index = 0
        self._play_current_track()
    
    def advance_track(self):
        """Advance to the next track in the shuffled playlist."""
        if not self.music_enabled or not self.shuffled_tracks:
            return
        
        self.current_index = (self.current_index + 1) % len(self.shuffled_tracks)
        self._play_current_track()
    
    def _play_current_track(self):
        """Load and play the track at the current index.
        
        Attempts to play the current track, falling back to the next track
        if the current one fails to load.
        """
        if not self.music_enabled or not self.shuffled_tracks:
            return
        
        track_count = len(self.shuffled_tracks)
        for offset in range(track_count):
            candidate_index = (self.current_index + offset) % track_count
            track_path = self.shuffled_tracks[candidate_index]
            try:
                pygame.mixer.music.load(track_path)
                pygame.mixer.music.play()
                self.current_index = candidate_index
                return
            except pygame.error:
                continue
        
        # All tracks failed to load
        self.music_enabled = False
    
    def get_shuffled_playlist(self):
        """Return the current shuffled playlist order.
        
        Returns:
            list: The shuffled track list (for debugging/display purposes)
        """
        return list(self.shuffled_tracks)
