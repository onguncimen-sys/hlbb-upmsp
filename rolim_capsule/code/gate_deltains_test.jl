#=
DOGRULUK KAPISI (rakip paketi; on-kayit protokolu "rakip dogruluk kapisi" maddesi).
DeltaIns hizli-delta formulunu, ayni kodun kesin yeniden hesabiyla (MachineSpan) karsilastirir.
Hamle kumesi Insertion() ile ayni (MR = en yuklu makine; MI = diger makineler; tum PR x PI).
ExecuteIns spani her hamleden sonra kesin yeniden hesapladigi icin RAPORLANAN makespan her
zaman dogrudur; sapma yalniz ARAMAYI yaniltir (iyilestiren hamle reddi / hayalet iyilestirme).

Kullanim:  julia -t 1 gate_deltains_test.jl <ALG.jl-yolu> [pure|nis] [seed]
Cikti:     GATE_RESULT alg=<dosya> mod=<mod> fix=<0/1> moves=<N> mismatch=<k> \
           rejected_improving=<r> ghost_improving=<g> maxabs=<d>
Kapi kurali (protokol): DELTAINS_FIX=1 ile mismatch=0 ZORUNLU (gecemezse duzeltme yanlis);
yayimlanmis surumde (fix=0) sapma BEKLENIR ve kayit icin olculur — surum secimi performansa
gore DEGIL, yayimli tanima birebirlige gore yapilir.
=#
include(ARGS[1])
using Random

function span_of(Sol::Vector{Vector{Int16}}, M::Int, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    if hasmethod(MachineSpan, Tuple{Vector{Vector{Int16}}, Int8, Matrix{Int16}, Vector{Matrix{Int16}}})
        return MachineSpan(Sol, Int8(M), p, S)      # HGA imzasi
    else
        return MachineSpan(Int8(M), p, S, Sol)      # GA imzasi
    end
end

function main()
    mode = length(ARGS) >= 2 ? ARGS[2] : "pure"
    seed = length(ARGS) >= 3 ? parse(Int, ARGS[3]) : 4242
    Random.seed!(seed)

    total = 0; mismatch = 0; rej = 0; ghost = 0; maxabs = 0
    for (m0, n0) in ((3, 12), (5, 20), (8, 40))
        m = Int8(m0); n = Int16(n0)
        p = Int16.(rand(1:99, m0, n0))
        S = Matrix{Int16}[Int16.([i == j ? 0 : rand(1:99) for i in 1:n0, j in 1:n0]) for _ in 1:m0]
        if mode == "nis"
            elig = [[rand() < 0.5 for _ in 1:m0] for _ in 1:n0]
            for j in 1:n0; elig[j][rand(1:m0)] = true; end       # her isin >= 1 uygun makinesi
            r = [rand(0:50) for _ in 1:m0]
            _set_niche!(m0, n0, r, elig)
        else
            _set_niche!(m0, n0, nothing, nothing)
        end
        for rep in 1:40
            # random solution (eligibility-respecting assignment + random order)
            Sol = Vector{Int16}[Int16[] for _ in 1:m0]
            for j in 1:n0
                macs = mode == "nis" ? [l for l in 1:m0 if _ok(j, l)] : collect(1:m0)
                push!(Sol[rand(macs)], Int16(j))
            end
            for l in 1:m0; shuffle!(Sol[l]); end
            O = Ind()
            O.Sol = Sol
            O.OF = Int32[span_of(Sol, l, p, S) for l in 1:m0]
            MR = Int8(argmax(O.OF))
            length(O.Sol[MR]) == 0 && continue
            for MI0 in 1:m0
                MI0 == Int(MR) && continue
                MI = Int8(MI0)
                for PR0 in eachindex(O.Sol[MR])
                    PR = Int16(PR0)
                    J = O.Sol[MR][PR]
                    mode == "nis" && !_ok(Int(J), MI0) && continue
                    for PI0 in 1:length(O.Sol[MI]) + 1
                        PI = Int16(PI0)
                        a_fast = DeltaIns(O, MR, MI, PR, PI, p, S)
                        # kesin yeniden hesap: hamleyi kopyada uygula (ExecuteIns ile ayni mekanik)
                        s2 = [copy(v) for v in O.Sol]
                        deleteat!(s2[MR], PR0); insert!(s2[MI], PI0, J)
                        Cai = span_of(s2, Int(MR), p, S); Caj = span_of(s2, Int(MI), p, S)
                        Cbi = O.OF[MR]; Cbj = O.OF[MI]
                        a_ex = max(Cbi, Cbj) > max(Cai, Caj) ? (Cbi - Cai) + (Cbj - Caj) : Int32(0)
                        total += 1
                        if a_fast != a_ex
                            mismatch += 1
                            a_ex > 0 && a_fast == 0 && (rej += 1)
                            a_ex == 0 && a_fast > 0 && (ghost += 1)
                            maxabs = max(maxabs, abs(Int(a_fast) - Int(a_ex)))
                        end
                    end
                end
            end
        end
    end
    println("GATE_RESULT alg=$(basename(ARGS[1])) mod=$mode fix=$(get(ENV, "DELTAINS_FIX", "0")) " *
            "moves=$total mismatch=$mismatch rejected_improving=$rej ghost_improving=$ghost maxabs=$maxabs")
end

main()
