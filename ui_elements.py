import pygame

class CardUI:

    def __init__(self, card_data, x, y):
        self.data = card_data
        self.x = x
        self.y = y
        self.width = 110  
        self.height = 160
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.font_name = pygame.font.SysFont("Arial", 14, bold=True)
        self.font_detail = pygame.font.SysFont("Arial", 12)
        self.is_disabled = False

    def wrap_text(self, text, font, max_width, max_lines):
        words = text.split()
        if not words:
            return []

        lines = []
        current_line = words[0]
        for word in words[1:]:
            candidate = f"{current_line} {word}"
            if font.size(candidate)[0] <= max_width:
                current_line = candidate
            else:
                lines.append(current_line)
                current_line = word
                if len(lines) >= max_lines - 1:
                    break
        if len(lines) < max_lines:
            lines.append(current_line)
        return lines[:max_lines]

    def draw(self, surface):
        pygame.draw.rect(surface, (255, 255, 255), self.rect)
        pygame.draw.rect(surface, (0, 0, 0), self.rect, 3)
        
        name_text = self.font_name.render(self.data["name"], True, (0, 0, 0))
        surface.blit(name_text, (self.x + 5, self.y + 10))

        if "suit" in self.data:
            suit_text = self.font_detail.render(f"Suit: {self.data['suit']}", True, (50, 50, 50))
            rank_text = self.font_detail.render(f"Rank: {self.data['rank']}", True, (200, 0, 0))
            surface.blit(suit_text, (self.x + 5, self.y + 40))
            surface.blit(rank_text, (self.x + 5, self.y + 60))
            
        elif "faction" in self.data:
            faction_text = self.font_detail.render(self.data["faction"], True, (0, 0, 150))
            surface.blit(faction_text, (self.x + 5, self.y + 40))
            power_lines = self.wrap_text(self.data.get("power", "Hero Power"), self.font_detail, self.width - 10, 6)
            y_pos = self.y + 60
            for line in power_lines:
                power_text = self.font_detail.render(line, True, (0, 100, 0))
                surface.blit(power_text, (self.x + 5, y_pos))
                y_pos += 14

        if self.is_disabled:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 170)) 
            surface.blit(overlay, (self.x, self.y))

    def is_clicked(self, mouse_pos):
        if self.is_disabled:
            return False
        return self.rect.collidepoint(mouse_pos)


class ButtonUI:
    def __init__(self, x, y, width, height, text, color):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.font = pygame.font.SysFont("Arial", 20)

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect, border_radius=5)
        text_surf = self.font.render(self.text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def is_clicked(self, mouse_pos):
        return self.rect.collidepoint(mouse_pos)
