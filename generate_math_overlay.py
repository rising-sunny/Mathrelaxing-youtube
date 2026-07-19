import matplotlib.pyplot as plt
import os

def create_equation_image():
    # Usar fuente estilo LaTeX (Computer Modern)
    plt.rcParams['mathtext.fontset'] = 'cm'
    
    # Establecer figura con fondo transparente (4 pulgadas x 120 dpi = 480px ancho, encaja en 576px)
    fig = plt.figure(figsize=(4, 0.8), dpi=120)
    fig.patch.set_alpha(0.0)
    
    # Expresión matemática
    formula = r"$A(r, \theta) = J_n(k \cdot r) \cos(n \theta)$"
    
    # Escribir la fórmula en blanco y más pequeña
    plt.text(0.5, 0.5, formula, fontsize=16, color="white", ha='center', va='center')
    
    plt.axis('off')
    
    # Guardar
    out_path = os.path.join(os.path.dirname(__file__), "output", "circular_cymatics", "bessel_formula.png")
    plt.savefig(out_path, transparent=True, bbox_inches='tight', pad_inches=0.1)
    print("Fórmula generada en:", out_path)

if __name__ == "__main__":
    create_equation_image()
