"""Reviewed Windows x64 emulator targets for the embedded-metadata patch.

Exact hashes identify release assets; unique loader/metadata-reader fingerprints
handle matching unverified builds. See SUPPORTED_BUILDS for official release URLs.
"""
PROFILES = {
    '245e350c32af4d91f852b11d9b301ee2f57ff74cf98cbcd0fc25853627a0a106':
        {'name':'PokeDinner 2.0.0 · 70ecb39ef0 · Windows x64', 'file':'eglantine.exe', 'abi':'msvc-read9',
         'hook':0x2fe638,'expected':'4c8d7dc04c89f9','kind':'inline-pokedinner'},
    'e3ec0b859e6e1ff2dec03865a3c8a11b547ad84521898091e21ab1c40d3927ec':
        {'name':'PokeDinner 2.0.0 · 70ecb39ef0 · Windows x64 CLI', 'file':'eden-cli.exe', 'abi':'msvc-read9',
         'hook':0x79458,'expected':'4c8d7dc04c89f9','kind':'inline-pokedinner'},
    '1528c11cff882d5b8b7d0dda83b57925700201b55f13471c8b62c79ea1275db8':
        {'name':'Eglantine build 96 · Windows x64', 'file':'eglantine.exe', 'abi':'msvc',
         'hook':0x459c40,'expected':'48895c2410','kind':'entry'},
    'cb89d931b603f604afe552ace6bbdde1a4dbbcf6431919b04c739043e30d19d4':
        {'name':'Eglantine build 96 · Windows x64 CLI', 'file':'eden-cli.exe', 'abi':'msvc',
         'hook':0x293020,'expected':'48895c2410','kind':'entry'},
    'a5e408544daa7a20d9506024410a468cb235cdedcfb9a6a7a8c9c2bcce43a8a0':
        {'name':'Eglantine build 96 · Windows x64 PGO', 'file':'eglantine.exe', 'abi':'gnu',
         'hook':0x1f6ea,'expected':'488d8c2480010000','kind':'inline'},
    '37f8ad2a67e6b6faf6f1d513d1adac12c5bfb144cf6bb53807bda008f059c7e7':
        {'name':'Eglantine build 96 · Windows x64 PGO CLI', 'file':'eden-cli.exe', 'abi':'gnu',
         'hook':0x1f92a,'expected':'488d8c2480010000','kind':'inline'},
}

# Official Windows assets checked on 2026-11-01.
PROFILES.update({'8a7d642b771e86a2b5ea7a01cfe4cae843fa0ef42e63d36adf29c74e21bd0f46': {'name': 'Eglantine AMD Experimental 77-2 · build-99 · Windows x64', 'file': 'eglantine.exe', 'abi': 'msvc', 'hook': 4561792, 'expected': '48895c2410', 'kind': 'entry'}, 'fc72e73e57c69fd49e37ba23cc666bc52c93655b823bd8eda73db043eca661e8': {'name': 'Eglantine AMD Experimental 77-2 · build-99 · Windows x64 CLI', 'file': 'eden-cli.exe', 'abi': 'msvc', 'hook': 2699296, 'expected': '48895c2410', 'kind': 'entry'}, '706a29bec23c290d6266c02ed5d7f7309f1311f00008e91ec90e699184d5e168': {'name': 'Eglantine AMD Experimental 77-2 · build-99 · Windows x64 PGO', 'file': 'eglantine.exe', 'abi': 'gnu', 'hook': 128394, 'expected': '488d8c2480010000', 'kind': 'inline'}, 'ef8c6edb004836975d0b9d5e31ed1b86d46a0bf3cecdaa21be1b42f73e94c9fa': {'name': 'Eglantine AMD Experimental 77-2 · build-99 · Windows x64 PGO CLI', 'file': 'eden-cli.exe', 'abi': 'gnu', 'hook': 128970, 'expected': '488d8c2480010000', 'kind': 'inline'}, '2b082c0ebe192f14675f277c537c8503cdeab8c2ec4c5b6a05cb460dbfaf82b1': {'name': 'Eglantine nx2 build 98 · adae763 · Windows x64', 'file': 'eglantine.exe', 'abi': 'msvc', 'hook': 4561984, 'expected': '48895c2410', 'kind': 'entry'}, 'c563fd0ed22d00743d292fd2d8b8f53d809bdd3b64f7a3707cba357a0aece38b': {'name': 'Eglantine nx2 build 98 · adae763 · Windows x64 CLI', 'file': 'eden-cli.exe', 'abi': 'msvc', 'hook': 2699296, 'expected': '48895c2410', 'kind': 'entry'}, '27316ad961d92671a1f67851c82871e7fe597ca20bed79b2a2d0c2746fd1a734': {'name': 'Eglantine nx2 build 98 · adae763 · Windows x64 PGO', 'file': 'eglantine.exe', 'abi': 'gnu', 'hook': 128746, 'expected': '488d8c2480010000', 'kind': 'inline'}, '569755d7dcf8691165b6283bbff562bdcd45356eae79881dee5c3dc665950d27': {'name': 'Eglantine nx2 build 98 · adae763 · Windows x64 PGO CLI', 'file': 'eden-cli.exe', 'abi': 'gnu', 'hook': 129322, 'expected': '488d8c2480010000', 'kind': 'inline'}, 'c7e829d5b3d9610ab2961e3835b6464ad332c8fdb15820143fce57507b30c955': {'name': 'PokeDinner 2.1.0a · Windows x64', 'file': 'eglantine.exe', 'abi': 'msvc-read9', 'hook': 3139128, 'expected': '4c8d7dc04c89f9', 'kind': 'inline-pokedinner'}, '54807b5a6bf65c8af6c3c10a0aab63b9e8903ad27025ac69921cb9b59780b3f0': {'name': 'PokeDinner 2.1.0a · Windows x64 CLI', 'file': 'eden-cli.exe', 'abi': 'msvc-read9', 'hook': 496728, 'expected': '4c8d7dc04c89f9', 'kind': 'inline-pokedinner'}})

# Selevet normal and 30 FPS archives contain the same reviewed executable.
PROFILES['b592bc3059f64dfe9e8d09e55a6bb780af9dca7149a7650f9d3e9450d856a96e'] = {'name': 'Selevet performance build 4 · normal / 30 FPS · Windows x64', 'file': 'eglantine.exe', 'abi': 'msvc-read9', 'hook': 26341599, 'expected': '4c8bbdb0030000', 'kind': 'inline-selevet', 'preserve_duplicate_unwind': True}

# Single catalog for the patch panel and documentation checks. These are patch
# targets, not a promise of game/FPS compatibility or arbitrary future versions.
SUPPORTED_BUILDS = (
    {'label':'Selevet performance build 4', 'variants':'normal + 30 FPS · GUI',
     'url':'https://github.com/sylvieistaken/selevet-eglantine/releases/tag/selevet-eglantine-performance-4'},
    {'label':'Eglantine nx2 build 98', 'variants':'standard + PGO · GUI/CLI',
     'url':'https://github.com/Djihads80/Eglantine/releases/tag/build-98'},
    {'label':'Eglantine AMD Experimental 77-2 (build-99)', 'variants':'standard + PGO · GUI/CLI',
     'url':'https://github.com/Djihads80/Eglantine/releases/tag/build-99'},
    {'label':'Eglantine nx2 build 96', 'variants':'standard + PGO · GUI/CLI',
     'url':'https://github.com/Djihads80/Eglantine/releases/tag/build-96'},
    {'label':'PokeDinner 2.1.0a (pre-release)', 'variants':'GUI/CLI',
     'url':'https://git.eden-emu.dev/Franseven/PokeDinner-a-Eglantine-Fork/releases/tag/2.1.0a'},
    {'label':'PokeDinner 2.0.0', 'variants':'GUI/CLI',
     'url':'https://git.eden-emu.dev/Franseven/PokeDinner-a-Eglantine-Fork/releases/tag/2.0.0'},
)
SUPPORT_CHECKED_DATE = '2026-11-02'
