#=
EQUIVALENCE HARNESS (SA nis-genisletmesi dogrulamasi).
Sabit-iterasyon (zaman-degil) -> deterministik. Ayni seed + ayni sabit-instance ile:
  extended-SA (pure mod) == original-SA  olmali (RNG-akisi birebir).
Kullanim: julia equiv_sa_test.jl <SA.jl-yolu> <alg_seed>
  -> stdout: EQUIV_RESULT <best_makespan> <checksum>
extended SA _set_niche! tanimliysa pure-modda cagrilir (r=M=nothing -> guard'lar no-op).
=#
include(ARGS[1])          # test edilecek SA.jl (orig ya da extended)
using Random

# ---- SABIT instance (her iki kosuda ozdes): seed 12345 ----
Random.seed!(12345)
m = Int8(5); n = Int16(40)
p = Int16.(rand(1:99, Int(m), Int(n)))
S = Matrix{Int16}[ Int16.([i == j ? 0 : rand(1:99) for i in 1:Int(n), j in 1:Int(n)]) for _ in 1:Int(m) ]

# extended ise pure-mod niche init (orig'de bu fonksiyon yok)
if isdefined(Main, :_set_niche!)
    _set_niche!(Int(m), Int(n), nothing, nothing)
end

# ---- algoritma RNG'si: verilen seed ----
# NOT: tum run mantigi bir fonksiyonda -> Julia global-scope'ta tip-bildirimli
# degiskene (best::Int32) izin vermiyor; local scope'ta sorun yok + soft-scope temiz.
function run_harness(seed_arg, m, n, p, S)
    Random.seed!(parse(Int, seed_arg))
    sol = InitialSolution(m, n)
    MS = zeros(Int32, Int(m))
    for i in 1:Int(m); MS[i] = MachineSpan(Int8(i), p, S, sol); end

    best::Int32 = maximum(MS)
    checksum::Int64 = 0
    for it in 1:20000
        LocalSearch(sol, MS, m, n, p, S)     # tum operatorleri RNG ile tetikler
        c::Int32 = maximum(MS)
        if c < best; best = c; end
        checksum += Int64(c)                  # trajektori parmak-izi (RNG-akisi sapmasini yakalar)
    end
    return best, checksum
end

best, checksum = run_harness(ARGS[2], m, n, p, S)
println("EQUIV_RESULT $best $checksum")
