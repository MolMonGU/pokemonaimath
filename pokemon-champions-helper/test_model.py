from ml.win_predictor import WinPredictor

wp = WinPredictor.load()

my_team = [
    "Kingambit",
    "Great Tusk",
    "Slowking-Galar",
    "Samurott-Hisui",
    "Iron Moth",
    "Zapdos",
]

opp_team = [
    "Blissey",
    "Corviknight",
    "Dondozo",
    "Gliscor",
    "Clefable",
    "Slowking-Galar",
]

prob = wp.predict_win_prob(my_team, opp_team)

print("내 팀 승리 확률:", round(prob * 100, 2), "%")
print("상대 팀 승리 확률:", round((1 - prob) * 100, 2), "%")
