#!/usr/bin/env python3
"""
Script de prueba para verificar la funcionalidad de tipos de impresora
"""

import sys
import logging
from lib.print_manager import print_queue_manager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_printer_types():
    """Prueba la funcionalidad de tipos de impresora"""
    print("=== Prueba de Tipos de Impresora ===\n")
    
    try:
        # Obtener lista de impresoras con información de tipo
        printers_info = print_queue_manager.get_available_printers_with_info()
        
        print(f"Encontradas {len(printers_info)} impresoras:\n")
        
        for i, printer_info in enumerate(printers_info, 1):
            name = printer_info['name']
            printer_type = printer_info['type']
            
            # Determinar el icono según el tipo
            type_icon = {
                'local': '🖨️',
                'network': '🌐', 
                'shared': '🔗'
            }.get(printer_type, '❓')
            
            print(f"{i:2d}. {type_icon} {name}")
            print(f"     Tipo: {printer_type}")
            
            # Verificar si es una impresora compartida (contiene \\)
            if '\\\\' in name:
                print(f"     ✓ Detectada como impresora de red/compartida")
            else:
                print(f"     ✓ Detectada como impresora local")
            print()
        
        # Probar también el método original
        print("\n=== Comparación con método original ===")
        original_printers = print_queue_manager.get_available_printers()
        print(f"Método original: {len(original_printers)} impresoras")
        print(f"Método nuevo: {len(printers_info)} impresoras")
        
        if len(original_printers) == len(printers_info):
            print("✓ Ambos métodos devuelven la misma cantidad de impresoras")
        else:
            print("⚠️ Diferencia en la cantidad de impresoras detectadas")
        
        print("\n=== Prueba completada exitosamente ===")
        return True
        
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_printer_types()
    sys.exit(0 if success else 1)