#!/usr/bin/env python3
"""
Inject auto-load script into Viciious HTML to automatically load and run a D64 disk image.
"""

import sys
import re

def inject_autoload(html_path, output_path, d64_filename):
    """
    Inject auto-load JavaScript into Viciious HTML.

    Args:
        html_path: Path to the original viciious.html
        output_path: Path to write the modified HTML
        d64_filename: Name of the D64 file to auto-load (e.g., 'spellcheck.d64')
    """

    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Create the auto-load script
    autoload_script = f'''
<script type="text/javascript">
// Auto-load {d64_filename} when the emulator is ready
(function() {{
    // Wait for c64 object to be available
    const checkReady = setInterval(() => {{
        if (window.c64 && window.c64.runloop) {{
            clearInterval(checkReady);

            // Give the emulator a moment to fully initialize
            setTimeout(() => {{
                console.log('Loading {d64_filename}...');

                fetch('{d64_filename}')
                    .then(response => {{
                        if (!response.ok) {{
                            throw new Error('Failed to load {d64_filename}: ' + response.statusText);
                        }}
                        return response.arrayBuffer();
                    }})
                    .then(buffer => {{
                        const bytes = new Uint8Array(buffer);

                        // Import ingest function from the bundled code
                        // Since everything is bundled, we need to call it via the module system
                        // The ingest function should be available through the c64 object's hooks

                        // Try to find the ingest function in the global scope
                        // It's defined in the webpack bundle, so we need to extract it
                        // For now, we'll use a workaround: trigger the drag-and-drop handler

                        // Create a mock drop event
                        const file = new File([bytes], '{d64_filename}', {{ type: 'application/octet-stream' }});
                        const dataTransfer = new DataTransfer();
                        dataTransfer.items.add(file);

                        const dropEvent = new DragEvent('drop', {{
                            bubbles: true,
                            cancelable: true,
                            dataTransfer: dataTransfer
                        }});

                        document.dispatchEvent(dropEvent);
                        console.log('{d64_filename} loaded successfully');
                    }})
                    .catch(error => {{
                        console.error('Error loading {d64_filename}:', error);
                        if (window.c64 && window.c64.hooks && window.c64.hooks.reportError) {{
                            window.c64.hooks.reportError('Failed to load {d64_filename}: ' + error.message);
                        }}
                    }});
            }}, 2000);  // Wait 2 seconds for full initialization
        }}
    }}, 100);  // Check every 100ms
}})();
</script>
'''

    # Inject before </body> or </html>
    if '</body>' in html:
        html = html.replace('</body>', autoload_script + '\n</body>')
    elif '</html>' in html:
        html = html.replace('</html>', autoload_script + '\n</html>')
    else:
        # Just append to the end
        html += autoload_script

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Injected auto-load script into {output_path}")
    print(f"Will automatically load: {d64_filename}")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: inject_autoload.py <input.html> <output.html> <file.d64>")
        sys.exit(1)

    inject_autoload(sys.argv[1], sys.argv[2], sys.argv[3])
